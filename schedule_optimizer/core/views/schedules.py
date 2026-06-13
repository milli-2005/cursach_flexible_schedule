"""Страницы просмотра, создания, редактирования и удаления графиков."""

from .auth import *
from .distribution_rules import _generate_studio_slots, _serialize_active_distribution_rules

@login_required
def create_schedule_view(request):
    """Готовит данные для страницы создания графика: даты, слоты, сотрудников и правила."""
    employee_models_with_workouts = Employee.objects.select_related('user_profile__user').prefetch_related('workout_types').filter(
        user_profile__role='employee',
        user_profile__user__is_active=True,
        workout_types__isnull=False,
    ).distinct()
    employees = UserProfile.objects.filter(
        id__in=employee_models_with_workouts.values_list('user_profile_id', flat=True)
    ).select_related('user')
    workout_types = WorkoutType.objects.all()

    # Генерация слотов (с учетом обеда 14:00-16:00)
    slots = _generate_studio_slots()

    # Build days for next week
    today = datetime.today()
    next_monday = today + timedelta(days=(7 - today.weekday()))
    current_days = [next_monday.date() + timedelta(days=i) for i in range(7)]

    # Строки для JS и шаблона
    date_strings = [d.strftime('%Y-%m-%d') for d in current_days]

    # Загрузка доступности, подготовка данных для быстрой проверки в JS
    availabilities = Availability.objects.filter(
        employee__in=employees,
        date__in=current_days,
        is_available=True,
    )

    # Создаём SET для быстрой проверки в JS: "emp_id,date,time"
    availability_set = set()
    for a in availabilities:
        key = f"{a.employee.id},{a.date.strftime('%Y-%m-%d')},{a.start_time.strftime('%H:%M')}"
        availability_set.add(key)
        
     # Получаем всех сотрудников с их направлениями
    employees_with_workouts = []
    for emp in employee_models_with_workouts:
        workouts = list(emp.workout_types.values('id', 'name', 'category'))
        user = emp.user_profile.user
        display_name = user.get_full_name().strip() or user.username
        employees_with_workouts.append({
            'id': emp.user_profile.id,
            'username': emp.user_profile.user.username,
            'display_name': display_name,
            'workout_types': workouts
        })

    missing_workout_profiles = UserProfile.objects.filter(
        role='employee',
        user__is_active=True,
    ).exclude(
        id__in=employees.values_list('id', flat=True)
    ).select_related('user')

    context = {
        'employees': employees,
        'workout_types': workout_types,
        'slots': slots,
        'days': current_days,
        'date_strings': date_strings,
        'availability_set_json': json.dumps(list(availability_set)),
        'employees_with_workouts_json': json.dumps(employees_with_workouts),
        'workout_types_json': json.dumps([
            {'id': wt.id, 'name': wt.name, 'category': wt.category} for wt in WorkoutType.objects.all()
        ]),
        'missing_workout_employees': [
            p.user.get_full_name().strip() or p.user.username for p in missing_workout_profiles
        ],
        'distribution_rules_json': json.dumps(_serialize_active_distribution_rules(), ensure_ascii=False),
    }
    
    return render(request, 'core/schedules/create_schedule.html', context)




from django.core.paginator import Paginator

@login_required
def schedule_view(request):
    """Показывает список графиков с фильтрами, сортировкой и статистикой согласования."""
    from django.db.models import Q

    if not hasattr(request.user, 'profile'):
        messages.error(request, "Профиль пользователя не найден.")
        return redirect('dashboard')

    # Параметры
    try:
        page_size = int(request.GET.get('page_size', 6))
    except (TypeError, ValueError):
        page_size = 6
    if page_size not in [6, 10, 20, 50]:
        page_size = 6

    sort_by = request.GET.get('sort', '-start_date')  # по умолчанию — новые сверху
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    creator_filter = request.GET.get('creator', '').strip()
    period_filter = request.GET.get('period', '').strip()
    approval_filter = request.GET.get('approval', '').strip()

    # Валидация поля сортировки
    valid_sort_fields = [
        'name', '-name',
        'start_date', '-start_date',
        'end_date', '-end_date',
        'status', '-status',
        'created_at', '-created_at',
    ]
    if sort_by not in valid_sort_fields:
        sort_by = '-start_date'

    # Запрос с сортировкой
    schedules = Schedule.objects.all().select_related('created_by').prefetch_related('approvals')

    if query:
        schedules = schedules.filter(
            Q(name__icontains=query) |
            Q(created_by__username__icontains=query) |
            Q(created_by__first_name__icontains=query) |
            Q(created_by__last_name__icontains=query)
        )

    if status_filter in {'draft', 'pending', 'approved'}:
        schedules = schedules.filter(status=status_filter)

    if creator_filter.isdigit():
        schedules = schedules.filter(created_by_id=int(creator_filter))

    today = timezone.localdate()
    if period_filter == 'current':
        schedules = schedules.filter(start_date__lte=today, end_date__gte=today)
    elif period_filter == 'upcoming':
        schedules = schedules.filter(start_date__gt=today)
    elif period_filter == 'past':
        schedules = schedules.filter(end_date__lt=today)

    schedules = schedules.order_by(sort_by)

    total_employees = UserProfile.objects.filter(role='employee').count()

    # Аннотации
    schedules_with_stats = []
    for s in schedules:
        approved_count = s.approvals.filter(approved=True).count()
        rejected_count = s.approvals.filter(approved=False).count()
        responded_count = s.approvals.filter(approved__isnull=False).count()

        schedules_with_stats.append({
            'schedule': s,
            'total_employees': total_employees,
            'approved_count': approved_count,
            'rejected_count': rejected_count,
            'responded_count': responded_count,
        })

    # Фильтр по состоянию согласования (после подсчёта статистики)
    if approval_filter in {'not_reviewed', 'partially_reviewed', 'fully_reviewed', 'with_rejections'}:
        filtered_stats = []
        for item in schedules_with_stats:
            responded = item['responded_count']
            rejected = item['rejected_count']

            if approval_filter == 'not_reviewed' and responded == 0:
                filtered_stats.append(item)
            elif approval_filter == 'partially_reviewed' and 0 < responded < total_employees:
                filtered_stats.append(item)
            elif approval_filter == 'fully_reviewed' and responded >= total_employees and total_employees > 0:
                filtered_stats.append(item)
            elif approval_filter == 'with_rejections' and rejected > 0:
                filtered_stats.append(item)
        schedules_with_stats = filtered_stats

    # Пагинация
    paginator = Paginator(schedules_with_stats, page_size)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    creators = User.objects.filter(
        id__in=Schedule.objects.exclude(created_by__isnull=True).values_list('created_by_id', flat=True).distinct()
    ).order_by('last_name', 'first_name', 'username')

    context = {
        'schedules_with_stats': page_obj,
        'page_obj': page_obj,
        'page_size': page_size,
        'current_sort': sort_by,
        'filter_q': query,
        'filter_status': status_filter,
        'filter_creator': creator_filter,
        'filter_period': period_filter,
        'filter_approval': approval_filter,
        'creators': creators,
    }
    return render(request, 'core/schedules/schedule_list.html', context)



@login_required
def schedule_detail(request, schedule_id):
    """Показывает подробную таблицу конкретного графика и данные для согласования."""
    schedule = get_object_or_404(Schedule, id=schedule_id)
    schedule_versions = schedule.versions.select_related('created_by').order_by('-version_number')[:30]

    # === 1. Генерация дней из графика ===
    days = []
    current_date = schedule.start_date
    while current_date <= schedule.end_date:
        days.append(current_date)
        current_date += timedelta(days=1)

    # === 2. Генерация временных слотов (9:00–21:00, без обеда 14:00-16:00) ===
    all_slots = [f"{start}–{end}" for start, end in _generate_studio_slots()]

    # === 3. Load all assignments in one query ===
    assignments = ShiftAssignment.objects.filter(
        schedule=schedule,
        date__in=days
    ).select_related('employee__user', 'workout_type')

    if (
        hasattr(request.user, 'profile')
        and request.user.profile.role in ['manager', 'studio_admin']
        and not schedule_versions
    ):
        bootstrap_version = ScheduleVersion.objects.create(
            schedule=schedule,
            version_number=1,
            schedule_name=schedule.name,
            created_by=request.user,
            change_source='bootstrap',
            change_note='Базовая версия для существующего графика',
        )
        snapshots = [
            ScheduleVersionAssignment(
                schedule_version=bootstrap_version,
                employee_id=a.employee_id,
                workout_type_id=a.workout_type_id,
                date=a.date,
                start_time=a.start_time,
                end_time=a.end_time,
            )
            for a in assignments
            if a.employee_id
        ]
        if snapshots:
            ScheduleVersionAssignment.objects.bulk_create(snapshots)
        schedule_versions = schedule.versions.select_related('created_by').order_by('-version_number')[:30]

    # === 4. Создание словаря: {(дата, время_начала): assignment} ===
    assignment_dict = {}
    for a in assignments:
        time_key = a.start_time.strftime('%H:%M')
        key = (a.date, time_key)
        assignment_dict[key] = a

    # === 5. Построение таблицы ===
    table_data = []
    for slot in all_slots:
        row = {'time_slot': slot, 'cells': []}
        start_time_str = slot.split('–')[0]

        for day in days:
            key = (day, start_time_str)
            assignment = assignment_dict.get(key)
            row['cells'].append({'assignment': assignment, 'date': day})
        table_data.append(row)

    # === 6. Данные для утверждения (только для сотрудников) ===
    approval_for_user = None
    approval_slots_for_user = []
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        if request.user.profile.role == 'employee':
            try:
                approval_for_user = ScheduleApproval.objects.get(
                    schedule=schedule,
                    employee=request.user.profile
                )
            except ScheduleApproval.DoesNotExist:
                approval_for_user = None
            user_shifts = ShiftAssignment.objects.filter(
                schedule=schedule,
                employee=request.user.profile,
            ).select_related('workout_type').order_by('date', 'start_time')
            approval_slots_for_user = [
                {
                    'date': sh.date.strftime('%Y-%m-%d'),
                    'date_label': sh.date.strftime('%d.%m.%Y'),
                    'start_time': sh.start_time.strftime('%H:%M'),
                    'time_slot': f"{sh.start_time.strftime('%H:%M')}-{sh.end_time.strftime('%H:%M')}",
                    'workout_name': sh.workout_type.name if sh.workout_type else 'Занятие',
                }
                for sh in user_shifts
            ]

    employee_models_with_workouts = Employee.objects.select_related('user_profile__user').prefetch_related('workout_types').filter(
        user_profile__role='employee',
        user_profile__user__is_active=True,
        workout_types__isnull=False,
    ).distinct()
    employees_with_workouts = []
    for emp in employee_models_with_workouts:
        workouts = list(emp.workout_types.values('id', 'name', 'category'))
        user = emp.user_profile.user
        display_name = user.get_full_name().strip() or user.username
        employees_with_workouts.append({
            'id': emp.user_profile.id,
            'username': emp.user_profile.user.username,
            'display_name': display_name,
            'workout_types': workouts,
        })

    availabilities = Availability.objects.filter(
        employee_id__in=employee_models_with_workouts.values_list('user_profile_id', flat=True),
        date__in=days,
        is_available=True,
    )
    availability_set = set()
    for a in availabilities:
        key = f"{a.employee.id},{a.date.strftime('%Y-%m-%d')},{a.start_time.strftime('%H:%M')}"
        availability_set.add(key)

    editable_employee_ids = list(
        employee_models_with_workouts.values_list('user_profile_id', flat=True)
    )

    schedule_edit_locked = False
    can_edit_schedule = (
        hasattr(request.user, 'profile')
        and request.user.profile.role in ['manager', 'studio_admin']
    )

    manager_rejections = []
    if hasattr(request.user, 'profile') and request.user.profile.role in ['manager', 'studio_admin']:
        rejected_approvals = (
            ScheduleApproval.objects
            .filter(schedule=schedule, approved=False)
            .select_related('employee__user')
            .order_by('-responded_at', '-id')
        )
        for appr in rejected_approvals:
            slots = appr.rejection_slots_json or []
            manager_rejections.append({
                'approval_id': appr.id,
                'employee_id': appr.employee_id,
                'employee_name': appr.employee.user.get_full_name() or appr.employee.user.username,
                'responded_at': appr.responded_at,
                'comment': appr.comment or '',
                'slots': slots,
            })

    context = {
        'schedule': schedule,
        'schedule_versions': schedule_versions,
        'days': days,
        'date_strings': [d.strftime('%Y-%m-%d') for d in days],
        'employees': UserProfile.objects.filter(
            id__in=editable_employee_ids
        ).select_related('user'),
        'editable_employee_ids': editable_employee_ids,
        'workout_types': WorkoutType.objects.all(),
        'employees_with_workouts_json': json.dumps(employees_with_workouts),
        'workout_types_json': json.dumps([
            {'id': wt.id, 'name': wt.name, 'category': wt.category} for wt in WorkoutType.objects.all()
        ]),
        'availability_set_json': json.dumps(list(availability_set)),
        'table_data': table_data,
        'approval_for_user': approval_for_user,
        'approval_slots_for_user_json': json.dumps(approval_slots_for_user, ensure_ascii=False),
        'manager_rejections': manager_rejections,
        'schedule_edit_locked': schedule_edit_locked,
        'can_edit_schedule': can_edit_schedule,
    }
    return render(request, 'core/schedules/view_schedule.html', context)




from collections import defaultdict

@login_required
def edit_schedule_view(request, schedule_id):
    """Готовит страницу редактирования графика с текущими сменами и доступностью сотрудников."""
    schedule = get_object_or_404(Schedule, id=schedule_id)

    # Генерация слотов (9:00–21:00, без обеда 14:00-16:00)
    slots = [f"{start} – {end}" for start, end in _generate_studio_slots()]

    # Генерация дней из графика
    from datetime import timedelta
    days = []
    current_date = schedule.start_date
    while current_date <= schedule.end_date:
        days.append(current_date)
        current_date += timedelta(days=1)

    date_strings = [d.strftime('%Y-%m-%d') for d in days]

    employee_models_with_workouts = Employee.objects.select_related('user_profile__user').prefetch_related('workout_types').filter(
        user_profile__role='employee',
        user_profile__user__is_active=True,
        workout_types__isnull=False,
    ).distinct()
    employees = UserProfile.objects.filter(
        id__in=employee_models_with_workouts.values_list('user_profile_id', flat=True)
    ).select_related('user')
    workout_types = WorkoutType.objects.all()

    # Текущие назначения
    assignments = ShiftAssignment.objects.filter(schedule=schedule).select_related('employee', 'workout_type')
    assignment_dict = defaultdict(dict)
    for a in assignments:
        time_key = a.start_time.strftime('%H:%M')
        assignment_dict[a.date][time_key] = a

    # === Load local data for rendering ===
    availabilities = Availability.objects.filter(
        employee__in=employees,
        date__in=days,
        is_available=True,
    )
    availability_set = set()
    for a in availabilities:
        key = f"{a.employee.id},{a.date.strftime('%Y-%m-%d')},{a.start_time.strftime('%H:%M')}"
        availability_set.add(key)

    context = {
        'schedule': schedule,
        'slots': slots,
        'days': days,
        'date_strings': date_strings,  # ← для JS
         'date_strings_json': json.dumps([d.strftime('%Y-%m-%d') for d in days]),
        'employees': employees,
        'workout_types': workout_types,
        'assignment_dict': dict(assignment_dict),
        'availability_set_json': json.dumps(list(availability_set)),  # ← для JS
    }
    return render(request, 'core/schedules/edit_schedule.html', context)



@login_required
@user_passes_test(is_manager)
def delete_schedule_view(request, schedule_id):
    """Удаляет график по POST-запросу и возвращает пользователя к списку графиков."""
    schedule = get_object_or_404(Schedule, id=schedule_id)
    if request.method == "POST":
        schedule_name = schedule.name
        schedule.delete()
        messages.success(request, f'График "{schedule_name}" успешно удалён.')
        return redirect('schedule_view')  # Перенаправление на список графиков
    # Если кто-то попытается GET — перенаправим на просмотр
    return redirect('view_schedule', schedule_id=schedule_id)




""" === EMPLOYEE SCHEDULE === """
from datetime import date, timedelta
import calendar
import json
from django.utils.html import escapejs
from django.utils import timezone

@login_required
def employee_schedule(request):
    """Показывает сотруднику его личные смены и графики, требующие подтверждения."""
    if not hasattr(request.user, 'profile'):
        return redirect('dashboard')

    today = date.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except (TypeError, ValueError):
        year, month = today.year, today.month

    if month < 1:
        year -= 1
        month = 12
    elif month > 12:
        year += 1
        month = 1

    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)

    all_dates = [first_day + timedelta(days=i) for i in range((last_day - first_day).days + 1)]

    assignments = ShiftAssignment.objects.filter(
        employee__user=request.user,
        date__gte=first_day,
        date__lte=last_day
    ).select_related('workout_type').order_by('date', 'start_time')

    shifts_by_date = {}
    for d in all_dates:
        shifts_by_date[d] = []
    for shift in assignments:
        shifts_by_date[shift.date].append(shift)

    # Подготовка JSON для JS
    shifts_json = {}
    for d, shifts in shifts_by_date.items():
        shifts_json[d.isoformat()] = [
            {
                'id': shift.id,
                'workout': escapejs(shift.workout_type.name if shift.workout_type else 'Работа'),
                'start': shift.start_time.strftime('%H:%M') if shift.start_time else '',
                'end': shift.end_time.strftime('%H:%M') if shift.end_time else '',
                'is_past': shift.date < today,
            }
            for shift in shifts
        ]

    cal = calendar.monthcalendar(year, month)
    weeks = []
    for week in cal:
        week_days = []
        for day in week:
            if day == 0:
                week_days.append(None)
            else:
                d = date(year, month, day)
                week_days.append({
                    'date': d,
                    'has_shift': len(shifts_by_date.get(d, [])) > 0,
                    'is_today': d == today,
                    'is_past': d < today,
                })
        weeks.append(week_days)

    # === Графики на утверждение ===
    pending_approvals = []
    if request.user.profile.role == 'employee':
        today_local = timezone.localdate()
        days_to_next_monday = (7 - today_local.weekday()) % 7
        if days_to_next_monday == 0:
            days_to_next_monday = 7
        next_week_start = today_local + timedelta(days=days_to_next_monday)
        next_week_end = next_week_start + timedelta(days=6)

        pending_approvals = ScheduleApproval.objects.filter(
            employee=request.user.profile,
            approved__isnull=True,
            schedule__status='pending',
            schedule__start_date__lte=next_week_end,
            schedule__end_date__gte=next_week_start,
        ).select_related('schedule').order_by('schedule__start_date', 'schedule__id')

    context = {
        'current_year': year,
        'current_month': month,
        'month_name': first_day.strftime('%B %Y'),
        'weeks': weeks,
        'shifts_by_date': shifts_by_date,
        'today': today,
        'shifts_json': json.dumps(shifts_json, ensure_ascii=False),
        'pending_approvals': pending_approvals,  # ← Теперь переменная определена!
    }

    return render(request, 'core/schedules/employee_schedule.html', context)




""" === ДОСТУПНОСТЬ === """

# core/views.py
from datetime import datetime, timedelta
