# core/api_schedule_views.py
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404
from datetime import datetime, timedelta
from django.utils.dateparse import parse_date
from django.core.mail import send_mail
from django.conf import settings

from .models import Schedule, ShiftAssignment, UserProfile, WorkoutType, ScheduleApproval, Availability
from django.utils import timezone


def is_manager(user):
    if not hasattr(user, 'profile'):
        return False
    return user.profile.role in ['manager', 'studio_admin']


@login_required
@user_passes_test(is_manager)
@csrf_exempt
@require_http_methods(["PUT"])
def api_update_schedule(request, schedule_id):
    try:
        schedule = get_object_or_404(Schedule, id=schedule_id)
        data = json.loads(request.body)
        assignments = data.get('assignments', [])

        # === 1. Получаем старые смены ===
        old_shifts = list(ShiftAssignment.objects.filter(schedule=schedule))
        old_by_key = {}
        old_employee_shifts = {}  # Сотрудник -> его смены
        for s in old_shifts:
            key = (s.employee_id, s.date, s.start_time)
            old_by_key[key] = s
            if s.employee_id:
                if s.employee_id not in old_employee_shifts:
                    old_employee_shifts[s.employee_id] = []
                old_employee_shifts[s.employee_id].append(key)

        # === 2. Удаляем старые смены ===
        ShiftAssignment.objects.filter(schedule=schedule).delete()

        # === 3. Создаём новые смены ===
        new_shifts = []
        new_by_key = {}
        new_employee_shifts = {}  # Сотрудник -> его смены
        for item in assignments:
            date_str = item['date']
            time_slot = item['time_slot']
            # === ВАЖНО: преобразуем employee_id в int ===
            employee_id = item.get('employee_id')
            if employee_id:
                employee_id = int(employee_id)
            workout_type_id = item.get('workout_type_id')
            if workout_type_id:
                workout_type_id = int(workout_type_id)

            if not employee_id and not workout_type_id:
                continue

            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            parts = time_slot.split('–')
            start_time_str = parts[0].strip()
            end_time_str = parts[1].strip() if len(parts) > 1 else None

            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.strptime(end_time_str, '%H:%M').time() if end_time_str else None

            if end_time is None:
                fake_dt = datetime.combine(datetime.min, start_time)
                end_dt = fake_dt + timedelta(minutes=50)
                end_time = end_dt.time()

            shift = ShiftAssignment.objects.create(
                schedule=schedule,
                date=date_obj,
                start_time=start_time,
                end_time=end_time,
                employee_id=employee_id,
                workout_type_id=workout_type_id
            )
            new_shifts.append(shift)
            key = (employee_id, date_obj, start_time)
            new_by_key[key] = shift
            if employee_id:
                if employee_id not in new_employee_shifts:
                    new_employee_shifts[employee_id] = []
                new_employee_shifts[employee_id].append(key)

        # === 4. Определяем, кто ИЗМЕНИЛСЯ ===
        changed_employees = set()

        # Случай 1: сотрудник был, но все его смены исчезли
        for emp_id in old_employee_shifts:
            if emp_id not in new_employee_shifts:
                changed_employees.add(emp_id)

        # Случай 2: сотрудник появился (новый)
        for emp_id in new_employee_shifts:
            if emp_id not in old_employee_shifts:
                changed_employees.add(emp_id)

        # Случай 3: сотрудник остался, но его смены изменились
        for emp_id in old_employee_shifts:
            if emp_id in new_employee_shifts:
                old_keys = set(old_employee_shifts[emp_id])
                new_keys = set(new_employee_shifts[emp_id])

                # Если набор смен изменился
                if old_keys != new_keys:
                    changed_employees.add(emp_id)

                # Или если тип тренировки изменился в оставшихся сменах
                else:
                    for key in old_keys:
                        old_shift = old_by_key[key]
                        new_shift = new_by_key[key]
                        if old_shift.workout_type_id != new_shift.workout_type_id:
                            changed_employees.add(emp_id)
                            break

        # === 5. Сбрасываем утверждение ТОЛЬКО для изменённых ===
        if changed_employees:
            ScheduleApproval.objects.filter(
                schedule=schedule,
                employee__in=list(changed_employees)
            ).update(approved=None, comment='', responded_at=None)

        # === 6. Удаляем approvals для сотрудников, у которых больше нет смен ===
        emp_ids_with_shifts = {s.employee_id for s in new_shifts if s.employee_id}
        to_delete = ScheduleApproval.objects.filter(
            schedule=schedule
        ).exclude(
            employee_id__in=emp_ids_with_shifts
        )
        to_delete.delete()

        # === 7. Добавляем approvals для новых сотрудников (которых ещё нет) ===
        existing = set(ScheduleApproval.objects.filter(schedule=schedule).values_list('employee_id', flat=True))
        new_approvals = []
        for emp_id in emp_ids_with_shifts - existing:
            if emp_id:
                new_approvals.append(ScheduleApproval(
                    schedule=schedule,
                    employee_id=emp_id,
                    approved=None
                ))

        if new_approvals:
            ScheduleApproval.objects.bulk_create(new_approvals)

        # === 8. Отправляем уведомления ТОЛЬКО измененным сотрудникам ===
        if changed_employees:
            changed_employees_objs = UserProfile.objects.filter(id__in=changed_employees)
            employee_emails = [emp.user.email for emp in changed_employees_objs if emp.user.email]
            if employee_emails:
                try:
                    send_mail(
                        subject="График был изменен и требует повторного подтверждения",
                        message=f"График '{schedule.name}' был изменен. Пожалуйста, подтвердите изменения.",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=employee_emails,
                    )
                except Exception as e:
                    print(f"[EMAIL ERROR] {e}")

        return JsonResponse({'success': True, 'changed_employees': list(changed_employees)})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# === Вспомогательная функция: копирование доступности с прошлой недели ===
def copy_availability_from_previous_week(employee, current_week_start):
    prev_week_start = current_week_start - timedelta(weeks=1)
    prev_avail = Availability.objects.filter(
        employee=employee,
        date__gte=prev_week_start,
        date__lt=prev_week_start + timedelta(days=7)
    )
    new_records = []
    for a in prev_avail:
        new_date = a.date + timedelta(weeks=1)
        new_records.append(Availability(
            employee=employee,
            date=new_date,
            start_time=a.start_time,
            end_time=a.end_time,
            is_available=True
        ))
    if new_records:
        Availability.objects.bulk_create(new_records, ignore_conflicts=True)


@login_required
@user_passes_test(is_manager)
@csrf_exempt
@require_http_methods(["POST"])
def api_save_schedule(request):
    try:
        data = json.loads(request.body.decode('utf-8'))

        # Создаём график со статусом "На согласовании"
        schedule = Schedule.objects.create(
            name=data['name'],
            start_date=parse_date(data['start_date']),
            end_date=parse_date(data['end_date']),
            created_by=request.user,
            status='pending'  # ← сразу на согласование
        )

        # Сохраняем назначения
        employee_ids_with_shifts = set()  # Собираем только тех, у кого есть смены
        for assignment_data in data['assignments']:
            employee = UserProfile.objects.get(id=assignment_data['employee_id'])
            employee_ids_with_shifts.add(employee.id)
            workout_type = None
            if assignment_data.get('workout_type_id'):
                workout_type = WorkoutType.objects.get(id=assignment_data['workout_type_id'])

            time_slot = assignment_data['time_slot']  # "09:00 – 09:50"
            parts = time_slot.split('–')
            start_time_str = parts[0].strip()
            end_time_str = parts[1].strip()

            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.strptime(end_time_str, '%H:%M').time()

            ShiftAssignment.objects.create(
                schedule=schedule,
                employee=employee,
                workout_type=workout_type,
                date=parse_date(assignment_data['date']),
                start_time=start_time,
                end_time=end_time
            )

        # === Создаём записи для согласования ТОЛЬКО для тех, у кого есть смены ===
        for emp_id in employee_ids_with_shifts:
            emp = UserProfile.objects.get(id=emp_id)
            ScheduleApproval.objects.get_or_create(
                schedule=schedule,
                employee=emp
            )

        # === Отправка email только тем, у кого есть смены ===
        employees_with_shifts = UserProfile.objects.filter(id__in=employee_ids_with_shifts)
        employee_emails = [emp.user.email for emp in employees_with_shifts if emp.user.email]
        if employee_emails:
            try:
                send_mail(
                    subject="Новый график на согласование",
                    message=f"График '{schedule.name}' ожидает вашего подтверждения. У вас есть 1 час.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=employee_emails,
                )
            except Exception as e:
                # Логируем ошибку, но не прерываем сохранение
                print(f"[EMAIL ERROR] {e}")

        return JsonResponse({'success': True, 'schedule_id': schedule.id})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)



# === Чтобы подтвердить или отклонить график ===
@login_required
@require_http_methods(["POST"])
def api_approve_schedule(request, schedule_id):
    try:
        schedule = get_object_or_404(Schedule, id=schedule_id)
        employee = request.user.profile

        if employee.role != 'employee':
            return JsonResponse({'success': False, 'error': 'Доступно только для сотрудников.'})

        data = json.loads(request.body)
        approved = data.get('approved', True)
        comment = data.get('comment', '').strip() if not approved else ''

        approval, created = ScheduleApproval.objects.update_or_create(
            schedule=schedule,
            employee=employee,
            defaults={
                'approved': approved,
                'comment': comment,
                'responded_at': timezone.now()
            }
        )

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})