"""Страница отчетов по часам, сменам, направлениям, ставкам и активности сотрудников."""

from .auth import *

""" === ОТЧЕТЫ === """
import json
from datetime import date, datetime, timedelta
from collections import defaultdict
import statistics
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from ..models import ShiftAssignment, UserProfile, WorkoutType, HourRateChange
from ..exports.operational_excel import _resolve_hour_rate_for_shift, _round_half_up_to_int

@login_required
def reports_view(request):
    """Собирает данные отчетов по часам, зарплате, направлениям, нагрузке и обменам сменами."""
    user = request.user
    profile = user.profile

    # === Detect current user role ===
    is_manager = (profile.role == 'manager')

    # Если не менеджер — показываем только его данные
    if not is_manager:
        employee_filter = profile  # текущий пользователь
    else:
        employee_id = request.GET.get('employee')
        if employee_id and employee_id != 'all':
            try:
                employee_filter = UserProfile.objects.get(id=employee_id, role='employee')
            except UserProfile.DoesNotExist:
                employee_filter = None
        else:
            employee_filter = None  # все сотрудники

    latest_rate = HourRateChange.objects.order_by('-created_at').first()
    hour_rate = float(latest_rate.rate) if latest_rate else None

    # Изменение ставки: только руководитель.
    if 'set_hour_rate' in request.GET:
        if not is_manager:
            messages.error(request, "Изменять часовую ставку может только руководитель.")
        else:
            new_rate_str = request.GET.get('hour_rate', '').strip()
            if new_rate_str:
                try:
                    new_rate = float(new_rate_str.replace(',', '.'))
                    if new_rate >= 0:
                        HourRateChange.objects.create(
                            rate=new_rate,
                            effective_from=timezone.now(),
                            changed_by=request.user,
                        )
                        hour_rate = new_rate
                        messages.success(
                            request,
                            f"Ставка изменена на {int(new_rate) if new_rate.is_integer() else new_rate} ₽/час. "
                            "Новая ставка применяется только к будущим сменам."
                        )
                    else:
                        messages.error(request, "Ставка не может быть отрицательной.")
                except ValueError:
                    messages.error(request, "Введите корректное число.")

    # === PERIOD ===
    period = request.GET.get('period', 'month')
    # === Resolve period ===
    today = date.today()

    # По умолчанию — текущий месяц
    default_start = today.replace(day=1)
    if today.month == 12:
        default_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        default_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

    # Получаем параметры из запроса
    period = request.GET.get('period', 'month')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    # Initialize dates with defaults
    start_date = default_start
    end_date = default_end

    # Обработка кастомного периода
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            period = 'custom'
        except ValueError:
            messages.error(request, "Неверный формат даты. Используйте формат ГГГГ-ММ-ДД.")
    elif period == 'week':
        start_date = today - timedelta(days=7)
        end_date = today
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(month=12, day=31)
    # else: остаётся 'month' -> уже задан как default

    delta = end_date - start_date
    all_dates = [start_date + timedelta(days=i) for i in range(delta.days + 1)]

    # === Apply custom date range (if provided) ===
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            period = 'custom'  # чтобы отличать от week/month/year
        except ValueError:
            messages.error(request, "Неверный формат даты. Используйте формат ГГГГ-ММ-ДД.")
            start_date = None
            end_date = None
    else:
        # Старая логика для period
        today = date.today()
        if period == 'week':
            start_date = today - timedelta(days=7)
            end_date = today
        elif period == 'month':
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        elif period == 'year':
            start_date = today.replace(month=1, day=1)
            end_date = today.replace(month=12, day=31)
        else:
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)



    # === Нормализация периода (фикс залипания custom-дат) ===
    # В форме скрытые start_date/end_date отправляются всегда, даже когда выбран week/month/year.
    # Поэтому учитываем их только если period=custom.
    today = date.today()
    period = request.GET.get('period', 'month')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if period == 'week':
        start_date = today - timedelta(days=7)
        end_date = today
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(month=12, day=31)
    elif period == 'custom':
        try:
            if not start_date_str or not end_date_str:
                raise ValueError("missing_custom_dates")
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            if start_date > end_date:
                start_date, end_date = end_date, start_date
        except ValueError:
            messages.error(request, "Для произвольного периода укажите корректные даты 'С' и 'По'.")
            period = 'month'
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    else:
        # month (по умолчанию)
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

    delta = end_date - start_date
    all_dates = [start_date + timedelta(days=i) for i in range(delta.days + 1)]

    # === Manager filters ===
    workout_id = request.GET.get('workout')
    search_query = request.GET.get('search', '').strip()
    coverage_direction = request.GET.get('coverage_direction', 'all')
    coverage_sort = request.GET.get('coverage_sort', 'trainers_desc')

    # === Filter application ===
    if is_manager:
        all_employees = UserProfile.objects.filter(role='employee').order_by('user__username')
        if employee_filter:
            employees = [employee_filter]
        else:
            employees = all_employees
    else:
        # Сотрудник — только он сам
        all_employees = [profile]
        employees = [profile]

    # === SHIFT QUERY ===
    assignments_base = ShiftAssignment.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).select_related('employee', 'workout_type')
    assignments = assignments_base

    # Применяем фильтры
    if is_manager:
        if employee_filter:
            assignments = assignments.filter(employee=employee_filter)
        if workout_id and workout_id != 'all':
            assignments = assignments.filter(workout_type_id=workout_id)
        if search_query:
            assignments = assignments.filter(
                Q(employee__user__username__icontains=search_query) |
                Q(workout_type__name__icontains=search_query)
            )
    else:
        # Сотрудник: только свои + фильтр по типу занятия
        assignments = assignments.filter(employee=profile)
        if workout_id and workout_id != 'all':
            assignments = assignments.filter(workout_type_id=workout_id)
        # Поиск не нужен — только свои данные

    # === Aggregation ===
    period_end_moment = datetime.combine(end_date, datetime.max.time())
    if timezone.is_naive(period_end_moment):
        period_end_moment = timezone.make_aware(period_end_moment, timezone.get_current_timezone())
    rate_changes = list(
        HourRateChange.objects.filter(effective_from__lte=period_end_moment)
        .order_by('-effective_from', '-id')
        .values_list('effective_from', 'rate')
    )
    rate_changes = [(dt, float(rate)) for dt, rate in rate_changes]

    from collections import defaultdict
    data = defaultdict(lambda: defaultdict(float))
    emp_hours = defaultdict(float)
    emp_salary = defaultdict(float)
    day_hours = [0.0] * 7
    workout_hours = defaultdict(float)
    date_hours = defaultdict(float)
    salary_available = False

    for a in assignments:
        if a.start_time is None or a.end_time is None:
            continue
        dur_raw = (datetime.combine(date.min, a.end_time) - datetime.combine(date.min, a.start_time)).total_seconds() / 3600
        dur = _round_half_up_to_int(dur_raw)
        data[a.employee_id][a.date] += dur
        emp_hours[a.employee.user.username] += dur
        day_hours[a.date.weekday()] += dur
        workout_hours[a.workout_type.name] += dur
        date_hours[a.date] += dur
        rate = _resolve_hour_rate_for_shift(a.date, a.start_time, rate_changes)
        if rate is not None:
            emp_salary[a.employee_id] += dur * rate
            salary_available = True

    total_hours = {}
    total_shifts = {}
    for emp in employees:
        emp_id = emp.id
        hours = sum(data[emp_id].values())
        shifts = sum(1 for v in data[emp_id].values() if v > 0)
        total_hours[emp.id] = int(round(hours))
        total_shifts[emp.id] = shifts

    daily_totals = []
    for d in all_dates:
        total = sum(data[emp.id].get(d, 0) for emp in employees)
        daily_totals.append(int(total))

    total_salary_per_emp = {}
    for emp in employees:
        total_salary_per_emp[emp.id] = int(round(emp_salary.get(emp.id, 0)))

    total_salary = int(round(sum(total_salary_per_emp.values())))

    # === Charts ===
    chart_data = {
        'empNames': list(emp_hours.keys()) or [],
        'empValues': [int(round(v)) for v in emp_hours.values()] or [],
        'dayLabels': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
        'dayValues': [int(round(v)) for v in day_hours] or [0]*7,
        'workoutLabels': list(workout_hours.keys()) or [],
        'workoutValues': [int(round(v)) for v in workout_hours.values()] or [],
        'dateLabels': [d.strftime('%d.%m') for d in sorted(date_hours.keys())] or [],
        'dateValues': [int(round(date_hours[d])) for d in sorted(date_hours.keys())] or [],
    }

    # === Direction summary for manager ===
    direction_rows = []
    employees_direction_rows = []
    direction_summary = {}
    workout_types_all = WorkoutType.objects.all().order_by('name')
    staff_rows = []
    staff_sort = request.GET.get('staff_sort', 'hours_desc')
    staff_peak_filter = request.GET.get('staff_peak_day', 'all')
    staff_swap_filter = request.GET.get('staff_swap_level', 'all')
    staff_search_raw = request.GET.get('staff_search', '').strip()
    staff_search = staff_search_raw.lower()

    if is_manager:
        def _display_name(user_profile):
            """Собирает читаемое имя пользователя из фамилии, имени, отчества или логина."""
            user_obj = user_profile.user
            full_name = f"{user_obj.last_name} {user_obj.first_name}".strip()
            return full_name if full_name else user_obj.username

        all_employee_profiles = UserProfile.objects.filter(
            role='employee'
        ).select_related('user', 'employee_profile').prefetch_related('employee_profile__workout_types')

        # Кто какие направления ведет
        direction_to_trainers = {wt.id: [] for wt in workout_types_all}
        employees_without_directions = []

        for emp_profile in all_employee_profiles:
            emp_obj = getattr(emp_profile, 'employee_profile', None)
            if not emp_obj:
                continue

            trainer_name = _display_name(emp_profile)
            trainer_workouts = list(emp_obj.workout_types.all())

            if not trainer_workouts:
                employees_without_directions.append(trainer_name)

            employees_direction_rows.append({
                'name': trainer_name,
                'workout_names': [w.name for w in trainer_workouts],
                'workout_count': len(trainer_workouts),
            })

            for wt in trainer_workouts:
                direction_to_trainers.setdefault(wt.id, []).append(trainer_name)

        # Нагрузка по направлениям за выбранный период
        direction_assignments = assignments_base
        if employee_filter:
            direction_assignments = direction_assignments.filter(employee=employee_filter)

        direction_hours = defaultdict(float)
        direction_shifts = defaultdict(int)
        for shift in direction_assignments:
            if not shift.workout_type_id:
                continue
            if shift.start_time is None or shift.end_time is None:
                continue
            duration_raw = (
                datetime.combine(date.min, shift.end_time) -
                datetime.combine(date.min, shift.start_time)
            ).total_seconds() / 3600
            duration = _round_half_up_to_int(duration_raw)
            direction_hours[shift.workout_type_id] += duration
            direction_shifts[shift.workout_type_id] += 1

        for wt in workout_types_all:
            if coverage_direction != 'all' and str(wt.id) != str(coverage_direction):
                continue
            trainers = sorted(direction_to_trainers.get(wt.id, []))
            direction_rows.append({
                'id': wt.id,
                'name': wt.name,
                'trainers': trainers,
                'trainers_count': len(trainers),
                'hours': int(round(direction_hours.get(wt.id, 0))),
                'shifts': direction_shifts.get(wt.id, 0),
            })

        if coverage_sort == 'trainers_asc':
            direction_rows.sort(key=lambda x: (x['trainers_count'], x['name'].lower()))
        elif coverage_sort == 'hours_desc':
            direction_rows.sort(key=lambda x: (-x['hours'], x['name'].lower()))
        elif coverage_sort == 'hours_asc':
            direction_rows.sort(key=lambda x: (x['hours'], x['name'].lower()))
        elif coverage_sort == 'name_asc':
            direction_rows.sort(key=lambda x: x['name'].lower())
        elif coverage_sort == 'name_desc':
            direction_rows.sort(key=lambda x: x['name'].lower(), reverse=True)
        else:
            direction_rows.sort(key=lambda x: (-x['trainers_count'], x['name'].lower()))

        covered_count = len([r for r in direction_rows if r['trainers_count'] > 0])
        direction_summary = {
            'total_directions': len(direction_rows),
            'covered_directions': covered_count,
            'uncovered_directions': len(direction_rows) - covered_count,
            'employees_without_directions_count': len(employees_without_directions),
            'employees_without_directions': employees_without_directions,
        }

        # === Staff analytics ===
        weekday_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

        assignments_for_staff = assignments_base
        if employee_filter:
            assignments_for_staff = assignments_for_staff.filter(employee=employee_filter)
        if workout_id and workout_id != 'all':
            assignments_for_staff = assignments_for_staff.filter(workout_type_id=workout_id)

        daily_hours_map = defaultdict(lambda: defaultdict(float))
        shifts_count_map = defaultdict(int)
        for shift in assignments_for_staff:
            if shift.start_time is None or shift.end_time is None:
                continue
            duration_raw = (
                datetime.combine(date.min, shift.end_time) -
                datetime.combine(date.min, shift.start_time)
            ).total_seconds() / 3600
            duration = _round_half_up_to_int(duration_raw)
            daily_hours_map[shift.employee_id][shift.date] += duration
            shifts_count_map[shift.employee_id] += 1

        period_schedules = Schedule.objects.filter(
            start_date__lte=end_date,
            end_date__gte=start_date,
        )

        approvals_qs = ScheduleApproval.objects.filter(
            schedule__in=period_schedules
        ).exclude(approved__isnull=True).select_related('employee')

        approval_map = defaultdict(lambda: {'responded': 0, 'rejected': 0})
        for approval in approvals_qs:
            approval_map[approval.employee_id]['responded'] += 1
            if approval.approved is False:
                approval_map[approval.employee_id]['rejected'] += 1

        swap_qs = ShiftSwapRequest.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            status__in=['approved_by_manager', 'completed']
        ).select_related('from_employee__user_profile', 'to_employee__user_profile')

        swap_involved_map = defaultdict(int)
        swap_sent_map = defaultdict(int)
        swap_received_map = defaultdict(int)
        for swap in swap_qs:
            from_profile_id = swap.from_employee.user_profile_id if swap.from_employee_id else None
            to_profile_id = swap.to_employee.user_profile_id if swap.to_employee_id else None
            if from_profile_id:
                swap_involved_map[from_profile_id] += 1
                swap_sent_map[from_profile_id] += 1
            if to_profile_id:
                swap_involved_map[to_profile_id] += 1
                swap_received_map[to_profile_id] += 1

        for emp_profile in all_employee_profiles:
            emp_id = emp_profile.id
            full_name = _display_name(emp_profile)
            login_name = emp_profile.user.username

            daily_items = daily_hours_map.get(emp_id, {})
            total_hours_emp = round(sum(daily_items.values()), 2)
            shifts_emp = shifts_count_map.get(emp_id, 0)
            worked_days = [h for h in daily_items.values() if h > 0]
            worked_days_count = len(worked_days)
            avg_per_workday = round(total_hours_emp / worked_days_count, 2) if worked_days_count else 0.0

            if worked_days_count >= 2:
                mean_val = statistics.mean(worked_days)
                std_val = statistics.pstdev(worked_days)
                cv = (std_val / mean_val) if mean_val > 0 else 1.0
                uniformity_score = max(0, round(100 - min(100, cv * 100), 1))
            elif worked_days_count == 1:
                uniformity_score = 100.0
            else:
                uniformity_score = 0.0

            peak_day_name = '—'
            if daily_items:
                peak_day_index, _ = max(
                    ((d.weekday(), hrs) for d, hrs in daily_items.items()),
                    key=lambda pair: pair[1]
                )
                peak_day_name = weekday_names[peak_day_index]

            approved_swaps = swap_involved_map.get(emp_id, 0)
            swaps_sent = swap_sent_map.get(emp_id, 0)
            swaps_received = swap_received_map.get(emp_id, 0)
            swap_frequency_pct = round((approved_swaps / shifts_emp) * 100, 1) if shifts_emp else 0.0

            responded = approval_map[emp_id]['responded']
            rejected = approval_map[emp_id]['rejected']
            rejection_pct = round((rejected / responded) * 100, 1) if responded else 0.0

            staff_rows.append({
                'employee_id': emp_id,
                'name': full_name,
                'username': login_name,
                'hours': total_hours_emp,
                'worked_days': worked_days_count,
                'avg_per_day': avg_per_workday,
                'uniformity': uniformity_score,
                'rejection_pct': rejection_pct,
                'rejected_count': rejected,
                'responded_count': responded,
                'swap_count': approved_swaps,
                'swap_sent': swaps_sent,
                'swap_received': swaps_received,
                'swap_frequency': swap_frequency_pct,
                'peak_day': peak_day_name,
            })

        if staff_peak_filter != 'all':
            staff_rows = [row for row in staff_rows if row['peak_day'] == staff_peak_filter]

        if staff_swap_filter == 'none':
            staff_rows = [row for row in staff_rows if row['swap_count'] == 0]
        elif staff_swap_filter == 'low':
            staff_rows = [row for row in staff_rows if 0 < row['swap_frequency'] <= 20]
        elif staff_swap_filter == 'high':
            staff_rows = [row for row in staff_rows if row['swap_frequency'] > 20]

        if staff_search:
            staff_rows = [
                row for row in staff_rows
                if staff_search in row['name'].lower() or staff_search in row['username'].lower()
            ]

        if staff_sort == 'hours_asc':
            staff_rows.sort(key=lambda x: (x['hours'], x['name'].lower()))
        elif staff_sort == 'uniformity_desc':
            staff_rows.sort(key=lambda x: (-x['uniformity'], x['name'].lower()))
        elif staff_sort == 'uniformity_asc':
            staff_rows.sort(key=lambda x: (x['uniformity'], x['name'].lower()))
        elif staff_sort == 'reject_desc':
            staff_rows.sort(key=lambda x: (-x['rejection_pct'], x['name'].lower()))
        elif staff_sort == 'swap_desc':
            staff_rows.sort(key=lambda x: (-x['swap_count'], x['name'].lower()))
        elif staff_sort == 'name_asc':
            staff_rows.sort(key=lambda x: x['name'].lower())
        else:
            staff_rows.sort(key=lambda x: (-x['hours'], x['name'].lower()))

    staff_chart = {
        'labels': [row['name'] for row in staff_rows[:12]],
        'hours': [row['hours'] for row in staff_rows[:12]],
        'uniformity': [row['uniformity'] for row in staff_rows[:12]],
        'rejection': [row['rejection_pct'] for row in staff_rows[:12]],
        'swaps': [row['swap_count'] for row in staff_rows[:12]],
    }

    staff_summary = {
        'trainers_count': len(staff_rows),
        'total_hours': round(sum((row.get('hours') or 0) for row in staff_rows), 1),
        'avg_uniformity': round(
            (sum((row.get('uniformity') or 0) for row in staff_rows) / len(staff_rows)),
            1
        ) if staff_rows else 0.0,
        'avg_rejection_pct': round(
            (sum((row.get('rejection_pct') or 0) for row in staff_rows) / len(staff_rows)),
            1
        ) if staff_rows else 0.0,
        'total_swaps': int(sum((row.get('swap_count') or 0) for row in staff_rows)),
    }

    context = {
        'start_date': start_date,
    'end_date': end_date,
    'period': period,
        'employee_id': getattr(employee_filter, 'id', 'all') if is_manager else 'self',
        'workout_id': workout_id or 'all',
        'search_query': search_query,
        'employees': employees,
        'all_employees': all_employees if is_manager else [],
        'workout_types': WorkoutType.objects.all(),
        'all_dates': all_dates,
        'data': data,
        'total_hours': total_hours,
        'total_shifts': total_shifts,
        'daily_totals': daily_totals,
        'total_all_hours': int(round(sum(total_hours.values()))),
        'total_all_assignments': assignments.count(),
        'active_employees': len(employees),
        'chart_data_json': json.dumps(chart_data, ensure_ascii=False),
        'hour_rate': hour_rate,
        'rate_last_changed_at': latest_rate.created_at if latest_rate else None,
        'total_salary': total_salary,
        'total_salary_per_emp': total_salary_per_emp,
        'salary_available': salary_available,
        'is_manager': is_manager,
        'coverage_direction': coverage_direction,
        'coverage_sort': coverage_sort,
        'direction_rows': direction_rows,
        'employees_direction_rows': employees_direction_rows,
        'direction_summary': direction_summary,
        'staff_rows': staff_rows,
        'staff_sort': staff_sort,
        'staff_peak_filter': staff_peak_filter,
        'staff_swap_filter': staff_swap_filter,
        'staff_search': staff_search_raw,
        'staff_chart_json': json.dumps(staff_chart, ensure_ascii=False),
        'staff_summary': staff_summary,
    }
    return render(request, 'core/reports/reports.html', context)
