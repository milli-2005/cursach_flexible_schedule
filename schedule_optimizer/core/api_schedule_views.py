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

        # Сначала удалим все текущие назначения для этого графика
        ShiftAssignment.objects.filter(schedule=schedule).delete()

        for item in assignments:
            date_str = item['date']          # "2026-01-22"
            time_str = item['time_slot']     # "09:00" ← ТОЛЬКО НАЧАЛО
            employee_id = item.get('employee_id')
            workout_type_id = item.get('workout_type_id')

            if not employee_id and not workout_type_id:
                continue  # пропускаем пустые

            # Преобразуем дату
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

            # Преобразуем время начала
            start_time_obj = datetime.strptime(time_str, '%H:%M').time()

            # Создаём новое назначение
            ShiftAssignment.objects.create(
                schedule=schedule,
                date=date_obj,
                start_time=start_time_obj,
                employee_id=employee_id,
                workout_type_id=workout_type_id
            )

        return JsonResponse({'success': True})

    except Exception as e:
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
        for assignment_data in data['assignments']:
            employee = UserProfile.objects.get(id=assignment_data['employee_id'])
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

        # === Создаём записи для согласования ===
        employees = UserProfile.objects.filter(role='employee')
        for emp in employees:
            ScheduleApproval.objects.get_or_create(
                schedule=schedule,
                employee=emp
            )

        # === Отправка email (в консоль) ===
        employee_emails = [emp.user.email for emp in employees if emp.user.email]
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