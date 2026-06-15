"""JSON API для сохранения графиков, версий, согласований и подбора замен."""

# core/api_schedule_views.py
import json
import logging
import re
import threading
import math
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..error_utils import api_error_response, humanize_exception
from ..email_utils import send_mail_with_fallback
from ..services.rule_ai_parser import try_parse_rule_with_ai
from ..models import (
    Availability,
    Employee,
    Schedule,
    ScheduleApproval,
    ScheduleVersion,
    ScheduleVersionAssignment,
    ShiftAssignment,
    UserProfile,
    WorkoutType,
)

logger = logging.getLogger(__name__)


def is_manager(user):
    """Проверяет, есть ли у пользователя роль руководителя для доступа к управленческим разделам."""
    if not hasattr(user, 'profile'):
        return False
    return user.profile.role == 'manager'


def _assert_schedule_editable(schedule: Schedule):
    """Заглушка для единообразной точки проверок редактирования графика."""
    return


def parse_time_slot(time_slot: str):
    """Разбирает строковый временной слот и возвращает время начала и окончания."""
    if not time_slot or not isinstance(time_slot, str):
        raise ValueError('Не удалось определить временной слот.')

    normalized = time_slot.strip().replace('–', '-').replace('—', '-')
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
    """Запускает отправку письма по графику в отдельном потоке, чтобы не задерживать HTTP-ответ."""
    recipient_list = [email for email in dict.fromkeys(recipient_list or []) if email]
    if not recipient_list:
        logger.warning("Email not sent: recipient list is empty. Subject: %s", subject)
        return

    def _job():
        """Выполняет фоновую отправку письма и логирует результат."""
        try:
            from_email = getattr(settings, 'EMAIL_HOST_USER', None) or settings.DEFAULT_FROM_EMAIL
            ok = send_mail_with_fallback(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=recipient_list,
            )
            if ok:
                logger.info("Email sent. Subject: %s; recipients: %s", subject, ", ".join(recipient_list))
            else:
                logger.error("Email send failed after fallback. Subject: %s", subject)
        except Exception as exc:
            logger.exception("Email send failed. Subject: %s; error: %s", subject, exc)

    threading.Thread(target=_job, daemon=True).start()


def _parse_optional_int(value, field_name: str):
    """Преобразует необязательное поле запроса в число или возвращает None."""
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f'Поле "{field_name}" должно быть числом.')


def _shift_signature(shift: ShiftAssignment):
    """Собирает устойчивую подпись смены для сравнения старого и нового состояния графика."""
    return (
        shift.employee_id,
        shift.date,
        shift.start_time,
        shift.end_time,
        shift.workout_type_id,
    )


def _create_schedule_version(schedule: Schedule, created_by=None, source: str = '', note: str = ''):
    """Создает снимок текущего графика, чтобы изменения можно было сравнивать и откатывать."""
    last_number = (
        ScheduleVersion.objects.filter(schedule=schedule)
        .order_by('-version_number')
        .values_list('version_number', flat=True)
        .first()
        or 0
    )
    version = ScheduleVersion.objects.create(
        schedule=schedule,
        version_number=last_number + 1,
        schedule_name=schedule.name,
        created_by=created_by if getattr(created_by, 'is_authenticated', False) else None,
        change_source=(source or '')[:30],
        change_note=(note or '')[:255],
    )

    current_assignments = ShiftAssignment.objects.filter(schedule=schedule)
    snapshot_rows = [
        ScheduleVersionAssignment(
            schedule_version=version,
            employee_id=assignment.employee_id,
            workout_type_id=assignment.workout_type_id,
            date=assignment.date,
            start_time=assignment.start_time,
            end_time=assignment.end_time,
        )
        for assignment in current_assignments
        if assignment.employee_id
    ]
    if snapshot_rows:
        ScheduleVersionAssignment.objects.bulk_create(snapshot_rows)
    return version


def _sync_schedule_approvals_and_notify(schedule: Schedule, old_shifts: list, new_shifts: list):
    """Обновляет согласования сотрудников после изменения графика и отправляет уведомления."""
    old_by_key = {}
    old_employee_shifts = {}
    for shift in old_shifts:
        key = (shift.employee_id, shift.date, shift.start_time)
        old_by_key[key] = shift
        if shift.employee_id:
            old_employee_shifts.setdefault(shift.employee_id, []).append(key)

    new_by_key = {}
    new_employee_shifts = {}
    for shift in new_shifts:
        key = (shift.employee_id, shift.date, shift.start_time)
        new_by_key[key] = shift
        if shift.employee_id:
            new_employee_shifts.setdefault(shift.employee_id, []).append(key)

    changed_employees = set()
    for emp_id in old_employee_shifts:
        if emp_id not in new_employee_shifts:
            changed_employees.add(emp_id)
    for emp_id in new_employee_shifts:
        if emp_id not in old_employee_shifts:
            changed_employees.add(emp_id)

    for emp_id in old_employee_shifts:
        if emp_id not in new_employee_shifts:
            continue
        old_keys = set(old_employee_shifts[emp_id])
        new_keys = set(new_employee_shifts[emp_id])
        if old_keys != new_keys:
            changed_employees.add(emp_id)
            continue
        for key in old_keys:
            if old_by_key[key].workout_type_id != new_by_key[key].workout_type_id:
                changed_employees.add(emp_id)
                break

    if changed_employees:
        ScheduleApproval.objects.filter(
            schedule=schedule,
            employee__in=list(changed_employees),
        ).update(approved=None, comment='', responded_at=None)

    employee_ids_with_shifts = {s.employee_id for s in new_shifts if s.employee_id}
    ScheduleApproval.objects.filter(schedule=schedule).exclude(
        employee_id__in=employee_ids_with_shifts
    ).delete()

    existing = set(ScheduleApproval.objects.filter(schedule=schedule).values_list('employee_id', flat=True))
    new_approvals = [
        ScheduleApproval(schedule=schedule, employee_id=emp_id, approved=None)
        for emp_id in (employee_ids_with_shifts - existing)
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

    return changed_employees


def _slot_to_time_slot(start_time):
    """Преобразует время начала в строку временного слота с окончанием через 50 минут."""
    end_time = (datetime.combine(datetime.min, start_time) + timedelta(minutes=50)).time()
    return f'{start_time.strftime("%H:%M")}-{end_time.strftime("%H:%M")}'


def _time_of_day_from_slot(start_time):
    """Определяет часть дня по времени начала слота: утро, день или вечер."""
    if start_time < datetime.strptime('14:00', '%H:%M').time():
        return 'morning'
    if start_time >= datetime.strptime('16:00', '%H:%M').time():
        return 'evening'
    return 'day'


def _parse_rejection_text_to_slot_hints(text: str):
    """Извлекает из текста отклонения подсказки по дням недели и частям суток."""
    lower = (text or '').lower()
    days = []
    day_map = {
        'понедельник': 0, 'пн': 0,
        'вторник': 1, 'вт': 1,
        'среда': 2, 'ср': 2,
        'четверг': 3, 'чт': 3,
        'пятница': 4, 'пт': 4,
        'суббота': 5, 'сб': 5,
        'воскресенье': 6, 'вс': 6,
    }
    for token, idx in day_map.items():
        if re.search(rf'\b{re.escape(token)}\b', lower):
            days.append(idx)
    days = sorted(set(days))

    parts = []
    if any(x in lower for x in ['утро', 'утром', 'до обеда']):
        parts.append('morning')
    if any(x in lower for x in ['вечер', 'вечером', 'после 16', 'после шести']):
        parts.append('evening')
    if any(x in lower for x in ['день', 'днем', 'днём']):
        parts.append('day')
    parts = list(dict.fromkeys(parts))
    return {'days': days, 'parts': parts}


def _build_candidate_rows(shift_date, time_slot, workout_type_id=None, schedule_id=None, exclude_employee_id=None, limit=3):
    """Подбирает сотрудников-кандидатов для замены с учетом доступности, нагрузки и направлений."""
    start_time, _ = parse_time_slot(time_slot)
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
    ).distinct()
    if exclude_employee_id:
        employee_qs = employee_qs.exclude(user_profile_id=exclude_employee_id)

    employee_profiles = list(employee_qs)
    if not employee_profiles:
        return []

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
        ).values('employee_id').annotate(total=Count('id'))
    }

    candidates = []
    seen_employee_ids = set()
    for employee in employee_profiles:
        employee_id = employee.user_profile_id
        if employee_id in seen_employee_ids:
            continue
        seen_employee_ids.add(employee_id)
        if employee_id in busy_ids:
            continue
        if schedule and employee_id in rejected_employee_ids:
            continue
        if availability_map.get(employee_id) is not True:
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
                    # Ищем направление той же категории
                    same_category = [wt for wt in workout_objects if wt.category == workout_type.category]
                    if same_category:
                        suggested_workout_type_id = same_category[0].id
                        suggested_workout_type_name = same_category[0].name
                    else:
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
            suggested_workout_type_id = workout_ids[0] if workout_ids else None
            suggested_workout_type_name = workout_objects[0].name if workout_ids else None

        user = employee.user_profile.user
        display_name = user.get_full_name().strip() or user.username
        candidates.append({
            'employee_id': employee_id,
            'username': user.username,
            'display_name': display_name,
            'score': score,
            'reasons': reasons,
            'suggested_workout_type_id': suggested_workout_type_id,
            'suggested_workout_type_name': suggested_workout_type_name,
        })

    candidates.sort(key=lambda item: (-item['score'], item['display_name'].lower()))
    return candidates[:max(1, min(int(limit or 3), 5))]


@login_required
@user_passes_test(is_manager)
@csrf_exempt
@require_http_methods(['POST'])
def api_substitute_candidates(request):
    """Возвращает кандидатов на замену для выбранного слота графика."""
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

        candidates = _build_candidate_rows(
            shift_date=shift_date,
            time_slot=time_slot,
            workout_type_id=workout_type_id,
            schedule_id=schedule_id,
            exclude_employee_id=exclude_employee_id,
            limit=limit,
        )

        return JsonResponse({
            'success': True,
            'candidates': candidates,
        })
    except Exception as exc:
        return api_error_response(exc, status=400)


@login_required
@user_passes_test(is_manager)
@csrf_exempt
@require_http_methods(['PUT'])
def api_update_schedule(request, schedule_id):
    """Обновляет график, пересоздает смены, согласования и версию при изменениях."""
    try:
        schedule = get_object_or_404(Schedule, id=schedule_id)
        _assert_schedule_editable(schedule)
        data = json.loads(request.body)
        schedule_name = (data.get('name') or '').strip()
        assignments = data.get('assignments', [])

        old_shifts = list(ShiftAssignment.objects.filter(schedule=schedule))
        old_name = schedule.name
        old_signature_set = {_shift_signature(s) for s in old_shifts}

        if schedule_name:
            schedule.name = schedule_name
            schedule.save(update_fields=['name', 'updated_at'])

        ShiftAssignment.objects.filter(schedule=schedule).delete()

        new_shifts = []
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

        changed_employees = _sync_schedule_approvals_and_notify(
            schedule=schedule,
            old_shifts=old_shifts,
            new_shifts=new_shifts,
        )

        new_signature_set = {_shift_signature(s) for s in new_shifts}
        has_structural_changes = old_signature_set != new_signature_set
        has_name_changes = old_name != schedule.name

        new_version = None
        if has_structural_changes or has_name_changes:
            new_version = _create_schedule_version(
                schedule=schedule,
                created_by=request.user,
                source='update',
                note='Изменения графика вручную',
            )

        return JsonResponse({
            'success': True,
            'changed_employees': list(changed_employees),
            'schedule_name': schedule.name,
            'version_number': new_version.version_number if new_version else None,
            'version_created': bool(new_version),
        })

    except Exception as exc:
        return api_error_response(exc, status=400)

@login_required
@user_passes_test(is_manager)
@csrf_exempt
@require_http_methods(['POST'])
def api_save_schedule(request):
    """Создает график, сохраняет назначения и отправляет сотрудникам запрос согласования."""
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

        first_version = _create_schedule_version(
            schedule=schedule,
            created_by=request.user,
            source='create',
            note='Первичное создание графика',
        )

        return JsonResponse({
            'success': True,
            'schedule_id': schedule.id,
            'version_number': first_version.version_number,
            'email_recipients_count': len(employee_emails),
            'warning': (
                'У сотрудников, добавленных в график, не заполнены email. '
                'Уведомления не отправлены.'
                if not employee_emails else ''
            ),
        })

    except Exception as exc:
        if schedule is not None and getattr(schedule, 'id', None):
            return JsonResponse({
                'success': True,
                'schedule_id': schedule.id,
                'warning': humanize_exception(exc),
            })
        return api_error_response(exc, status=400)


def _version_assignment_map(version: ScheduleVersion):
    """Преобразует назначения версии графика в словарь для сравнения версий."""
    result = {}
    rows = version.assignments.select_related('employee__user', 'workout_type').all()
    for row in rows:
        key = f"{row.date.isoformat()}|{row.start_time.strftime('%H:%M')}"
        employee_name = ''
        if row.employee_id:
            employee_name = row.employee.user.get_full_name().strip() or row.employee.user.username
        result[key] = {
            'date': row.date.isoformat(),
            'time': row.start_time.strftime('%H:%M'),
            'employee_id': row.employee_id,
            'employee_name': employee_name or '—',
            'workout_type_id': row.workout_type_id,
            'workout_name': row.workout_type.name if row.workout_type_id else '—',
        }
    return result


@login_required
@user_passes_test(is_manager)
@require_http_methods(['GET'])
def api_schedule_versions(request, schedule_id):
    """Возвращает историю версий выбранного графика."""
    schedule = get_object_or_404(Schedule, id=schedule_id)
    versions = (
        ScheduleVersion.objects.filter(schedule=schedule)
        .select_related('created_by')
        .annotate(assignments_count=Count('assignments'))
        .order_by('-version_number')
    )

    data = []
    for v in versions:
        if v.created_by_id:
            author = v.created_by.get_full_name().strip() or v.created_by.username
        else:
            author = 'system'
        data.append({
            'id': v.id,
            'version_number': v.version_number,
            'schedule_name': v.schedule_name,
            'change_source': v.change_source,
            'change_note': v.change_note,
            'created_at': timezone.localtime(v.created_at).strftime('%d.%m.%Y %H:%M'),
            'created_by': author,
            'assignments_count': v.assignments_count,
        })

    return JsonResponse({'success': True, 'versions': data})


@login_required
@user_passes_test(is_manager)
@require_http_methods(['GET'])
def api_compare_schedule_versions(request, schedule_id):
    """Сравнивает две версии графика и возвращает список отличий."""
    schedule = get_object_or_404(Schedule, id=schedule_id)
    left_id = request.GET.get('left_version_id')
    right_id = request.GET.get('right_version_id')
    if not left_id or not right_id:
        return JsonResponse({'success': False, 'error': 'Выберите две версии для сравнения.'}, status=400)
    try:
        left_id = int(left_id)
        right_id = int(right_id)
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Некорректные идентификаторы версий.'}, status=400)

    left = get_object_or_404(ScheduleVersion, id=left_id, schedule=schedule)
    right = get_object_or_404(ScheduleVersion, id=right_id, schedule=schedule)

    left_map = _version_assignment_map(left)
    right_map = _version_assignment_map(right)
    all_keys = sorted(set(left_map.keys()) | set(right_map.keys()))

    changes = []
    for key in all_keys:
        l = left_map.get(key)
        r = right_map.get(key)
        if l and not r:
            changes.append({
                'date': l['date'],
                'time': l['time'],
                'change_type': 'removed',
                'left': l,
                'right': None,
            })
            continue
        if r and not l:
            changes.append({
                'date': r['date'],
                'time': r['time'],
                'change_type': 'added',
                'left': None,
                'right': r,
            })
            continue
        if not l or not r:
            continue
        if l['employee_id'] != r['employee_id'] or l['workout_type_id'] != r['workout_type_id']:
            changes.append({
                'date': r['date'],
                'time': r['time'],
                'change_type': 'changed',
                'left': l,
                'right': r,
            })

    return JsonResponse({
        'success': True,
        'left_version': {'id': left.id, 'number': left.version_number, 'name': left.schedule_name},
        'right_version': {'id': right.id, 'number': right.version_number, 'name': right.schedule_name},
        'changes_count': len(changes),
        'changes': changes,
    })


@login_required
@user_passes_test(is_manager)
@csrf_exempt
@require_http_methods(['POST'])
def api_restore_schedule_version(request, schedule_id, version_id):
    """Восстанавливает график из выбранной версии и создает новую версию отката."""
    try:
        schedule = get_object_or_404(Schedule, id=schedule_id)
        _assert_schedule_editable(schedule)
        version = get_object_or_404(ScheduleVersion, id=version_id, schedule=schedule)

        old_shifts = list(ShiftAssignment.objects.filter(schedule=schedule))
        ShiftAssignment.objects.filter(schedule=schedule).delete()

        version_rows = version.assignments.all()
        restored_shifts = []
        for row in version_rows:
            if not row.employee_id:
                continue
            restored_shifts.append(
                ShiftAssignment.objects.create(
                    schedule=schedule,
                    employee_id=row.employee_id,
                    workout_type_id=row.workout_type_id,
                    date=row.date,
                    start_time=row.start_time,
                    end_time=row.end_time,
                )
            )

        if schedule.name != version.schedule_name:
            schedule.name = version.schedule_name
            schedule.save(update_fields=['name', 'updated_at'])

        changed_employees = _sync_schedule_approvals_and_notify(
            schedule=schedule,
            old_shifts=old_shifts,
            new_shifts=restored_shifts,
        )

        new_version = _create_schedule_version(
            schedule=schedule,
            created_by=request.user,
            source='restore',
            note=f'Откат к версии v{version.version_number}',
        )

        return JsonResponse({
            'success': True,
            'restored_to': version.version_number,
            'new_version': new_version.version_number,
            'changed_employees': list(changed_employees),
        })
    except Exception as exc:
        return api_error_response(exc, status=400)


@login_required
@require_http_methods(['POST'])
def api_approve_schedule(request, schedule_id):
    """Сохраняет ответ сотрудника по графику: подтверждение или отклонение."""
    try:
        schedule = get_object_or_404(Schedule, id=schedule_id)
        employee = request.user.profile

        if employee.role != 'employee':
            return JsonResponse({'success': False, 'error': 'Доступно только для сотрудников.'})

        data = json.loads(request.body)
        approved = data.get('approved', True)
        comment = data.get('comment', '').strip() if not approved else ''
        reject_mode = (data.get('reject_mode') or 'manual').strip()
        selected_slots = data.get('selected_slots') or []
        ai_text = (data.get('ai_text') or '').strip()

        if not approved and reject_mode not in {'manual', 'ai'}:
            return JsonResponse({'success': False, 'error': 'Некорректный режим отклонения.'}, status=400)
        if not approved and reject_mode == 'manual' and not selected_slots:
            return JsonResponse({'success': False, 'error': 'Выберите хотя бы один слот для отклонения.'}, status=400)
        if not approved and reject_mode == 'ai' and not ai_text:
            return JsonResponse({'success': False, 'error': 'Введите текст причины для AI-анализа.'}, status=400)

        details = None
        if not approved:
            details = _build_rejection_suggestions(
                schedule=schedule,
                employee=employee,
                reject_mode=reject_mode,
                selected_slots=selected_slots,
                ai_text=ai_text,
            )
            # Тренер только указывает недоступные слоты и причину.
            # Подбор и выбор конкретной замены выполняет руководитель.
            details.pop('candidates_preview', None)

        ScheduleApproval.objects.update_or_create(
            schedule=schedule,
            employee=employee,
            defaults={
                'approved': approved,
                'comment': comment,
                'rejection_slots_json': (details or {}).get('slots', []) if not approved else [],
                'responded_at': timezone.now(),
            },
        )

        return JsonResponse({
            'success': True,
            'details': details,
        })

    except Exception as exc:
        return api_error_response(exc, status=400)


def _build_rejection_suggestions(schedule, employee, reject_mode='manual', selected_slots=None, ai_text=''):
    """Формирует список слотов, по которым сотрудник просит замену при отклонении графика."""
    selected_slots = selected_slots or []
    shifts_qs = ShiftAssignment.objects.filter(
        schedule=schedule,
        employee=employee,
    ).select_related('workout_type').order_by('date', 'start_time')

    own_shift_map = {}
    for sh in shifts_qs:
        key = f'{sh.date.isoformat()}|{sh.start_time.strftime("%H:%M")}'
        own_shift_map[key] = sh

    picked_shifts = []
    if reject_mode == 'manual':
        for row in selected_slots:
            date_str = (row.get('date') or '').strip()
            time_str = (row.get('start_time') or '').strip()
            if not date_str or not time_str:
                continue
            key = f'{date_str}|{time_str}'
            sh = own_shift_map.get(key)
            if sh:
                picked_shifts.append(sh)
    else:
        hints = _parse_rejection_text_to_slot_hints(ai_text)
        days = set(hints.get('days') or [])
        parts = set(hints.get('parts') or [])
        for sh in own_shift_map.values():
            day_ok = True if not days else sh.date.weekday() in days
            part_ok = True if not parts else _time_of_day_from_slot(sh.start_time) in parts
            if day_ok and part_ok:
                picked_shifts.append(sh)

        if not picked_shifts and ai_text:
            # fallback: пробуем внешнее AI только как подсказку по дням/частям суток
            ai_try = try_parse_rule_with_ai(ai_text)
            if ai_try.get('success'):
                parsed = ai_try.get('parsed') or {}
                params = parsed.get('params_json') or {}
                days_hint = params.get('weekdays') or []
                day_set = set(int(d) for d in days_hint if isinstance(d, int))
                if day_set:
                    for sh in own_shift_map.values():
                        if sh.date.weekday() in day_set:
                            picked_shifts.append(sh)

    picked_shifts = sorted(set(picked_shifts), key=lambda s: (s.date, s.start_time))
    slot_rows = []
    for sh in picked_shifts:
        time_slot = _slot_to_time_slot(sh.start_time)
        slot_rows.append({
            'date': sh.date.isoformat(),
            'start_time': sh.start_time.strftime('%H:%M'),
            'time_slot': time_slot,
            'workout_type': sh.workout_type.name if sh.workout_type else '',
        })

    lines = []
    if slot_rows:
        lines.append('Слоты, которые сотрудник просит заменить:')
        for item in slot_rows:
            lines.append(f"- {item['date']} {item['time_slot']} ({item['workout_type']})")
    else:
        lines.append('По отклонению не удалось определить слоты для замены.')

    return {
        'mode': reject_mode,
        'slots_count': len(slot_rows),
        'slots': slot_rows,
        'summary_text': '\n'.join(lines),
    }


@login_required
@user_passes_test(is_manager)
@require_http_methods(['GET'])
def api_simulate_schedule_variants(request, schedule_id):
    """
    Прогон 3 вариантов на странице просмотра/редактирования.
    Учитывает замечания тренеров: смены сотрудников, которые отклонили график,
    считаются приоритетными для подбора замены.
    """
    try:
        schedule = get_object_or_404(Schedule, id=schedule_id)
        variants_count = 3
        shifts = list(
            ShiftAssignment.objects.filter(schedule=schedule)
            .select_related('workout_type')
            .order_by('date', 'start_time', 'id')
        )
        if not shifts:
            return JsonResponse({'success': True, 'variants': []})

        rejected_employee_ids = set(
            ScheduleApproval.objects.filter(
                schedule=schedule,
                approved=False,
            ).values_list('employee_id', flat=True)
        )

        def _plan_metrics(plan_map):
            """Считает простые метрики варианта графика: заполненность и баланс нагрузки."""
            loads = {}
            for item in plan_map.values():
                emp_id = item.get('employee_id')
                if not emp_id:
                    continue
                loads[emp_id] = loads.get(emp_id, 0) + 1
            arr = list(loads.values())
            if not arr:
                return {'avg_load': 0, 'balance_std': 0}
            avg = sum(arr) / len(arr)
            variance = sum((x - avg) ** 2 for x in arr) / len(arr)
            return {'avg_load': round(avg, 2), 'balance_std': round(math.sqrt(variance), 2)}

        variants = []
        for variant_idx in range(variants_count):
            plan = {}
            replaced_due_to_remarks = 0
            unresolved_remarks = 0

            for slot_idx, sh in enumerate(shifts):
                key = f'{sh.date.isoformat()}|{_slot_to_time_slot(sh.start_time)}'
                original_employee_id = sh.employee_id
                original_workout_id = sh.workout_type_id
                chosen_employee_id = original_employee_id
                chosen_workout_id = original_workout_id

                needs_reassign = (original_employee_id in rejected_employee_ids) or (original_employee_id is None)
                if needs_reassign:
                    candidates = _build_candidate_rows(
                        shift_date=sh.date,
                        time_slot=_slot_to_time_slot(sh.start_time),
                        workout_type_id=original_workout_id,
                        schedule_id=schedule.id,
                        exclude_employee_id=original_employee_id,
                        limit=5,
                    )
                    if candidates:
                        top_len = min(len(candidates), 3)
                        pick = candidates[(slot_idx + variant_idx) % top_len]
                        chosen_employee_id = int(pick['employee_id'])
                        chosen_workout_id = int(pick['suggested_workout_type_id']) if pick.get('suggested_workout_type_id') else original_workout_id
                        if original_employee_id and chosen_employee_id != original_employee_id:
                            replaced_due_to_remarks += 1
                    else:
                        if original_employee_id in rejected_employee_ids:
                            unresolved_remarks += 1

                plan[key] = {
                    'employee_id': str(chosen_employee_id) if chosen_employee_id else '',
                    'workout_type_id': str(chosen_workout_id) if chosen_workout_id else '',
                }

            metrics = _plan_metrics(plan)
            variants.append({
                'id': variant_idx + 1,
                'title': f'Вариант {variant_idx + 1}',
                'plan': plan,
                'metrics': {
                    'filled': sum(1 for v in plan.values() if v.get('employee_id')),
                    'replaced_due_to_remarks': replaced_due_to_remarks,
                    'unresolved_remarks': unresolved_remarks,
                    'avg_load': metrics['avg_load'],
                    'balance_std': metrics['balance_std'],
                },
            })

        return JsonResponse({'success': True, 'variants': variants})
    except Exception as exc:
        return api_error_response(exc, status=400)


@login_required
@user_passes_test(is_manager)
@csrf_exempt
@require_http_methods(['POST'])
def api_set_schedule_status(request, schedule_id):
    """Меняет статус графика и возвращает новое отображаемое состояние."""
    try:
        schedule = get_object_or_404(Schedule, id=schedule_id)
        data = json.loads(request.body or '{}')
        new_status = (data.get('status') or '').strip()
        allowed_statuses = {'draft', 'pending', 'approved'}
        if new_status not in allowed_statuses:
            return JsonResponse({'success': False, 'error': 'Некорректный статус графика.'}, status=400)

        schedule.status = new_status
        schedule.save(update_fields=['status', 'updated_at'])
        return JsonResponse({
            'success': True,
            'status': schedule.status,
            'status_display': schedule.get_status_display(),
        })
    except Exception as exc:
        return api_error_response(exc, status=400)
