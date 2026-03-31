# core/api_schedule_views.py
import json
import re
import threading
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.mail import send_mail
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .error_utils import api_error_response, humanize_exception
from .models import Availability, Employee, Schedule, ScheduleApproval, ShiftAssignment, UserProfile, WorkoutType


def is_manager(user):
    if not hasattr(user, 'profile'):
        return False
    return user.profile.role in ['manager', 'studio_admin']


def parse_time_slot(time_slot: str):
    if not time_slot or not isinstance(time_slot, str):
        raise ValueError('Не удалось определить временной слот.')

    normalized = time_slot.strip().replace('вЂ“', '-').replace('–', '-').replace('—', '-')
    parts = re.split(r'\s*-\s*', normalized, maxsplit=1)
    if not parts or not parts[0]:
        raise ValueError(f'Некорректный формат времени: {time_slot}')

    start_time = datetime.strptime(parts[0].strip(), '%H:%M').time()
    if len(parts) > 1 and parts[1].strip():
        end_time = datetime.strptime(parts[1].strip(), '%H:%M').time()
    else:
        end_time = (datetime.combine(datetime.min, start_time) + timedelta(minutes=50)).time()

    return start_time, end_time


def _send_schedule_email_async(subject: str, message: str, recipient_list: list[str]):
    if not recipient_list:
        return

    def _job():
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_list,
                fail_silently=True,
            )
        except Exception:
            pass

    threading.Thread(target=_job, daemon=True).start()


def _parse_optional_int(value, field_name: str):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f'Поле "{field_name}" должно быть числом.')


@login_required
@user_passes_test(is_manager)
@csrf_exempt
@require_http_methods(['POST'])
def api_substitute_candidates(request):
    try:
        data = json.loads(request.body.decode('utf-8'))

        shift_date = parse_date(data.get('date'))
        if not shift_date:
            raise ValueError('Укажите корректную дату слота для подбора замены.')

        time_slot = (data.get('time_slot') or '').strip()
        if not time_slot:
            raise ValueError('Укажите время слота для подбора замены.')
        start_time, _ = parse_time_slot(time_slot)

        workout_type_id = _parse_optional_int(data.get('workout_type_id'), 'workout_type_id')
        schedule_id = _parse_optional_int(data.get('schedule_id'), 'schedule_id')
        exclude_employee_id = _parse_optional_int(data.get('exclude_employee_id'), 'exclude_employee_id')
        limit = _parse_optional_int(data.get('limit'), 'limit') or 5
        limit = max(1, min(limit, 10))

        workout_type = None
        if workout_type_id:
            workout_type = WorkoutType.objects.filter(id=workout_type_id).first()
            if not workout_type:
                raise ValueError('Выбранное направление не найдено.')

        schedule = None
        rejected_employee_ids = set()
        if schedule_id:
            schedule = Schedule.objects.filter(id=schedule_id).first()
            if not schedule:
                raise ValueError('График для подбора замены не найден.')
            rejected_employee_ids = set(
                ScheduleApproval.objects.filter(
                    schedule=schedule,
                    approved=False,
                ).values_list('employee_id', flat=True)
            )

        employee_qs = Employee.objects.select_related('user_profile__user').prefetch_related('workout_types').filter(
            user_profile__role='employee',
            user_profile__user__is_active=True,
            workout_types__isnull=False,
        )
        if exclude_employee_id:
            employee_qs = employee_qs.exclude(user_profile_id=exclude_employee_id)

        employee_profiles = list(employee_qs)
        if not employee_profiles:
            return JsonResponse({'success': True, 'candidates': []})

        profile_ids = [emp.user_profile_id for emp in employee_profiles]

        busy_ids = set(
            ShiftAssignment.objects.filter(
                employee_id__in=profile_ids,
                date=shift_date,
                start_time=start_time,
            ).values_list('employee_id', flat=True)
        )

        availability_map = {
            row['employee_id']: row['is_available']
            for row in Availability.objects.filter(
                employee_id__in=profile_ids,
                date=shift_date,
                start_time=start_time,
            ).values('employee_id', 'is_available')
        }

        week_start = shift_date - timedelta(days=shift_date.weekday())
        week_end = week_start + timedelta(days=6)
        weekly_load_map = {
            row['employee_id']: row['total']
            for row in ShiftAssignment.objects.filter(
                employee_id__in=profile_ids,
                date__range=(week_start, week_end),
            )
            .values('employee_id')
            .annotate(total=Count('id'))
        }

        candidates = []
        for employee in employee_profiles:
            employee_id = employee.user_profile_id
            if employee_id in busy_ids:
                continue
            if schedule and employee_id in rejected_employee_ids:
                continue

            availability_status = availability_map.get(employee_id)
            # Подмена возможна только при явной отметке доступности на этот слот.
            if availability_status is not True:
                continue

            workout_objects = list(employee.workout_types.all())
            workout_ids = [wt.id for wt in workout_objects]

            weekly_slots = weekly_load_map.get(employee_id, 0)
            priority = int(employee.substitute_priority or 50)

            score = 0
            reasons = []

            if employee.is_substitute:
                score += 28
                reasons.append('входит в пул подмен')
            else:
                score += 8
                reasons.append('доступен как обычный кандидат')

            score += 26
            reasons.append('подтвердил доступность на этот слот')

            score += max(0, 25 - min(priority, 100) // 2)
            score += max(0, 20 - weekly_slots * 2)
            reasons.append(f'текущая нагрузка: {weekly_slots} слотов за неделю')

            if workout_type_id:
                if workout_type_id in workout_ids:
                    score += 18
                    reasons.append(f'ведет направление «{workout_type.name}»')
                    suggested_workout_type_id = workout_type_id
                    suggested_workout_type_name = workout_type.name
                else:
                    score -= 8
                    if workout_ids:
                        suggested_workout_type_id = workout_ids[0]
                        suggested_workout_type_name = workout_objects[0].name
                        reasons.append(
                            f'потребуется смена направления с «{workout_type.name}» на «{suggested_workout_type_name}»'
                        )
                    else:
                        suggested_workout_type_id = None
                        suggested_workout_type_name = None
                        reasons.append(f'потребуется смена направления «{workout_type.name}»')
            else:
                if workout_ids:
                    score += 4
                suggested_workout_type_id = workout_ids[0] if workout_ids else None
                suggested_workout_type_name = (
                    workout_objects[0].name if workout_ids else None
                )

            user = employee.user_profile.user
            display_name = user.get_full_name().strip() or user.username

            candidates.append({
                'employee_id': employee_id,
                'username': user.username,
                'display_name': display_name,
                'is_substitute': employee.is_substitute,
                'weekly_slots': weekly_slots,
                'score': score,
                'reasons': reasons,
                'suggested_workout_type_id': suggested_workout_type_id,
                'suggested_workout_type_name': suggested_workout_type_name,
            })

        candidates.sort(
            key=lambda item: (
                -item['score'],
                item['weekly_slots'],
                item['display_name'].lower(),
            )
        )

        return JsonResponse({
            'success': True,
            'candidates': candidates[:limit],
        })
    except Exception as exc:
        return api_error_response(exc, status=400)


@login_required
@user_passes_test(is_manager)
@csrf_exempt
@require_http_methods(['PUT'])
def api_update_schedule(request, schedule_id):
    try:
        schedule = get_object_or_404(Schedule, id=schedule_id)
        data = json.loads(request.body)
        assignments = data.get('assignments', [])

        old_shifts = list(ShiftAssignment.objects.filter(schedule=schedule))
        old_by_key = {}
        old_employee_shifts = {}
        for shift in old_shifts:
            key = (shift.employee_id, shift.date, shift.start_time)
            old_by_key[key] = shift
            if shift.employee_id:
                old_employee_shifts.setdefault(shift.employee_id, []).append(key)

        ShiftAssignment.objects.filter(schedule=schedule).delete()

        new_shifts = []
        new_by_key = {}
        new_employee_shifts = {}
        for item in assignments:
            date_str = item['date']
            time_slot = item['time_slot']
            employee_id = int(item['employee_id']) if item.get('employee_id') else None
            workout_type_id = int(item['workout_type_id']) if item.get('workout_type_id') else None

            if not employee_id and not workout_type_id:
                continue

            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            start_time, end_time = parse_time_slot(time_slot)

            if employee_id:
                can_be_scheduled = Employee.objects.filter(
                    user_profile_id=employee_id,
                    workout_types__isnull=False,
                ).exists()
                if not can_be_scheduled:
                    username = UserProfile.objects.filter(id=employee_id).values_list('user__username', flat=True).first() or str(employee_id)
                    raise ValueError(
                        f'Нельзя назначить сотрудника "{username}": у него не выбраны направления.'
                    )
                if workout_type_id:
                    has_workout = Employee.objects.filter(
                        user_profile_id=employee_id,
                        workout_types__id=workout_type_id,
                    ).exists()
                    if not has_workout:
                        username = UserProfile.objects.filter(id=employee_id).values_list('user__username', flat=True).first() or str(employee_id)
                        workout_name = WorkoutType.objects.filter(id=workout_type_id).values_list('name', flat=True).first() or str(workout_type_id)
                        raise ValueError(
                            f'Нельзя назначить "{workout_name}" сотруднику "{username}": это направление не закреплено в его профиле.'
                        )

            shift = ShiftAssignment.objects.create(
                schedule=schedule,
                date=date_obj,
                start_time=start_time,
                end_time=end_time,
                employee_id=employee_id,
                workout_type_id=workout_type_id,
            )
            new_shifts.append(shift)

            key = (employee_id, date_obj, start_time)
            new_by_key[key] = shift
            if employee_id:
                new_employee_shifts.setdefault(employee_id, []).append(key)

        changed_employees = set()

        for emp_id in old_employee_shifts:
            if emp_id not in new_employee_shifts:
                changed_employees.add(emp_id)

        for emp_id in new_employee_shifts:
            if emp_id not in old_employee_shifts:
                changed_employees.add(emp_id)

        for emp_id in old_employee_shifts:
            if emp_id in new_employee_shifts:
                old_keys = set(old_employee_shifts[emp_id])
                new_keys = set(new_employee_shifts[emp_id])
                if old_keys != new_keys:
                    changed_employees.add(emp_id)
                else:
                    for key in old_keys:
                        if old_by_key[key].workout_type_id != new_by_key[key].workout_type_id:
                            changed_employees.add(emp_id)
                            break

        if changed_employees:
            ScheduleApproval.objects.filter(
                schedule=schedule,
                employee__in=list(changed_employees),
            ).update(approved=None, comment='', responded_at=None)

        emp_ids_with_shifts = {s.employee_id for s in new_shifts if s.employee_id}
        ScheduleApproval.objects.filter(schedule=schedule).exclude(
            employee_id__in=emp_ids_with_shifts
        ).delete()

        existing = set(ScheduleApproval.objects.filter(schedule=schedule).values_list('employee_id', flat=True))
        new_approvals = [
            ScheduleApproval(schedule=schedule, employee_id=emp_id, approved=None)
            for emp_id in (emp_ids_with_shifts - existing)
            if emp_id
        ]
        if new_approvals:
            ScheduleApproval.objects.bulk_create(new_approvals)

        if changed_employees:
            changed_objs = UserProfile.objects.filter(id__in=changed_employees)
            emails = [emp.user.email for emp in changed_objs if emp.user.email]
            _send_schedule_email_async(
                subject='График был изменен и требует повторного подтверждения',
                message=f"График '{schedule.name}' был изменен. Пожалуйста, подтвердите изменения.",
                recipient_list=emails,
            )

        return JsonResponse({'success': True, 'changed_employees': list(changed_employees)})

    except Exception as exc:
        return api_error_response(exc, status=400)


def copy_availability_from_previous_week(employee, current_week_start):
    prev_week_start = current_week_start - timedelta(weeks=1)
    prev_avail = Availability.objects.filter(
        employee=employee,
        date__gte=prev_week_start,
        date__lt=prev_week_start + timedelta(days=7),
    )

    new_records = []
    for availability in prev_avail:
        new_records.append(
            Availability(
                employee=employee,
                date=availability.date + timedelta(weeks=1),
                start_time=availability.start_time,
                end_time=availability.end_time,
                is_available=True,
            )
        )

    if new_records:
        Availability.objects.bulk_create(new_records, ignore_conflicts=True)


@login_required
@user_passes_test(is_manager)
@csrf_exempt
@require_http_methods(['POST'])
def api_save_schedule(request):
    schedule = None
    try:
        data = json.loads(request.body.decode('utf-8'))

        schedule_name = (data.get('name') or '').strip()
        if not schedule_name:
            raise ValueError('Укажите название графика.')

        start_date = parse_date(data.get('start_date'))
        end_date = parse_date(data.get('end_date'))
        if not start_date or not end_date:
            raise ValueError('Некорректный диапазон дат графика.')
        if end_date < start_date:
            raise ValueError('Дата окончания не может быть раньше даты начала.')

        existing_schedule = Schedule.objects.filter(
            start_date=start_date,
            end_date=end_date,
        ).order_by('-created_at').first()
        if existing_schedule:
            period_start = start_date.strftime('%d.%m.%Y')
            period_end = end_date.strftime('%d.%m.%Y')
            raise ValueError(
                f'График на период {period_start} — {period_end} уже создан '
                f'(«{existing_schedule.name}»). Откройте его в списке графиков.'
            )

        assignments_data = data.get('assignments', [])
        if not isinstance(assignments_data, list):
            raise ValueError('Некорректный формат списка назначений.')

        schedule = Schedule.objects.create(
            name=schedule_name,
            start_date=start_date,
            end_date=end_date,
            created_by=request.user,
            status='pending',
        )

        employee_ids_with_shifts = set()
        for assignment_data in assignments_data:
            employee = UserProfile.objects.get(id=assignment_data['employee_id'])
            can_be_scheduled = Employee.objects.filter(
                user_profile=employee,
                workout_types__isnull=False,
            ).exists()
            if not can_be_scheduled:
                raise ValueError(
                    f'Нельзя назначить сотрудника "{employee.user.username}": у него не выбраны направления.'
                )
            employee_ids_with_shifts.add(employee.id)

            workout_type = None
            if assignment_data.get('workout_type_id'):
                workout_type = WorkoutType.objects.get(id=assignment_data['workout_type_id'])
                has_workout = Employee.objects.filter(
                    user_profile=employee,
                    workout_types=workout_type,
                ).exists()
                if not has_workout:
                    raise ValueError(
                        f'Нельзя назначить "{workout_type.name}" сотруднику "{employee.user.username}": это направление не закреплено в его профиле.'
                    )

            start_time, end_time = parse_time_slot(assignment_data.get('time_slot'))

            shift_date = parse_date(assignment_data.get('date'))
            if not shift_date:
                raise ValueError('Некорректная дата в назначениях.')

            ShiftAssignment.objects.create(
                schedule=schedule,
                employee=employee,
                workout_type=workout_type,
                date=shift_date,
                start_time=start_time,
                end_time=end_time,
            )

        for emp_id in employee_ids_with_shifts:
            ScheduleApproval.objects.get_or_create(
                schedule=schedule,
                employee=UserProfile.objects.get(id=emp_id),
            )

        employees_with_shifts = UserProfile.objects.filter(id__in=employee_ids_with_shifts)
        employee_emails = [emp.user.email for emp in employees_with_shifts if emp.user.email]
        _send_schedule_email_async(
            subject='Новый график на согласование',
            message=f"График '{schedule.name}' ожидает вашего подтверждения. У вас есть 1 час.",
            recipient_list=employee_emails,
        )

        return JsonResponse({'success': True, 'schedule_id': schedule.id})

    except Exception as exc:
        if schedule is not None and getattr(schedule, 'id', None):
            return JsonResponse({
                'success': True,
                'schedule_id': schedule.id,
                'warning': humanize_exception(exc),
            })
        return api_error_response(exc, status=400)


@login_required
@require_http_methods(['POST'])
def api_approve_schedule(request, schedule_id):
    try:
        schedule = get_object_or_404(Schedule, id=schedule_id)
        employee = request.user.profile

        if employee.role != 'employee':
            return JsonResponse({'success': False, 'error': 'Доступно только для сотрудников.'})

        data = json.loads(request.body)
        approved = data.get('approved', True)
        comment = data.get('comment', '').strip() if not approved else ''

        ScheduleApproval.objects.update_or_create(
            schedule=schedule,
            employee=employee,
            defaults={
                'approved': approved,
                'comment': comment,
                'responded_at': timezone.now(),
            },
        )

        return JsonResponse({'success': True})

    except Exception as exc:
        return api_error_response(exc, status=400)
