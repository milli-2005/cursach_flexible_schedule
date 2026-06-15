# Страница отчетов: часы, зарплата, направления, нагрузка, обмены сменами, аналитика по персоналу
# Основная view-функция reports_view() собирает все данные и передает в шаблон core/reports/reports.html

from .auth import *  # импорт декораторов и вспомогательных функций из соседнего модуля auth.py

# === ИМПОРТЫ ===
import json  # для сериализации данных графиков в JSON (chart_data_json, staff_chart_json)
from datetime import date, datetime, timedelta  # работа с датами (периоды отчёта, расчёт длительности)
from collections import defaultdict  # словарь со значением по умолчанию (часы, зарплата по сотрудникам)
import statistics  # для расчёта равномерности нагрузки (среднее, стандартное отклонение)
from django.shortcuts import render, redirect  # рендер шаблона и редирект
from django.contrib import messages  # flash-сообщения пользователю (ошибки/успех)
from django.contrib.auth.decorators import login_required  # требование авторизации
from django.db.models import Q  # для ORM-фильтра "ИЛИ" (поиск по имени или названию)
from ..models import ShiftAssignment, UserProfile, WorkoutType, HourRateChange  # модели БД
from ..exports.operational_excel import _resolve_hour_rate_for_shift, _round_half_up_to_int  # расчёт ставки и округление

@login_required  # доступ только авторизованным пользователям
def reports_view(request):
    # Собирает данные для страницы отчётов: часы, зарплату, направления, нагрузку, обмены сменами.
    user = request.user  # текущий пользователь (Person)
    profile = user.profile  # его профиль UserProfile (роль: manager/employee)

    # === ОПРЕДЕЛЕНИЕ РОЛИ ===
    is_manager = (profile.role == 'manager')  # True — руководитель, False — обычный сотрудник

    # Если не менеджер — показываем только его данные
    if not is_manager:
        employee_filter = profile  # сотрудник видит только себя
    else:
        # Менеджер может выбрать конкретного сотрудника через GET-параметр employee
        employee_id = request.GET.get('employee')
        if employee_id and employee_id != 'all':
            try:
                employee_filter = UserProfile.objects.get(id=employee_id, role='employee')
            except UserProfile.DoesNotExist:
                employee_filter = None  # если такого ID нет — показываем всех
        else:
            employee_filter = None  # None = все сотрудники

    # === ТЕКУЩАЯ ЧАСОВАЯ СТАВКА ===
    latest_rate = HourRateChange.objects.order_by('-created_at').first()  # последняя запись ставки
    hour_rate = float(latest_rate.rate) if latest_rate else None  # преобразуем Decimal во float или None

    # === ИЗМЕНЕНИЕ СТАВКИ ===
    # Проверяем, пришёл ли параметр set_hour_rate в GET-запросе (кнопка "Сохранить ставку")
    if 'set_hour_rate' in request.GET:
        if not is_manager:
            messages.error(request, "Изменять часовую ставку может только руководитель.")
        else:
            new_rate_str = request.GET.get('hour_rate', '').strip()  # строка из поля ввода
            if new_rate_str:
                try:
                    new_rate = float(new_rate_str.replace(',', '.'))  # запятая → точка
                    if new_rate >= 0:
                        # Создаём запись в истории ставок с моментом начала действия
                        HourRateChange.objects.create(
                            rate=new_rate,
                            effective_from=timezone.now(),  # действует с этого момента
                            changed_by=request.user,  # кто изменил
                        )
                        hour_rate = new_rate  # обновляем переменную для отображения в шаблоне
                        messages.success(
                            request,
                            f"Ставка изменена на {int(new_rate) if new_rate.is_integer() else new_rate} ₽/час. "
                            "Новая ставка применяется только к будущим сменам."
                        )
                    else:
                        messages.error(request, "Ставка не может быть отрицательной.")
                except ValueError:
                    messages.error(request, "Введите корректное число.")

    # === ПЕРИОД ОТЧЁТА ===
    period = request.GET.get('period', 'month')  # week / month / year / custom
    today = date.today()  # текущая дата для расчёта периода по умолчанию

    # По умолчанию — текущий месяц (первое и последнее число)
    default_start = today.replace(day=1)  # первое число месяца
    if today.month == 12:
        default_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)  # январь след. года - 1 день = 31 декабря
    else:
        default_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)  # первый день след. месяца - 1 день = последний день текущего

    # Считываем даты из GET-параметров
    period = request.GET.get('period', 'month')  # повторно (уже читали выше — исторический код)
    start_date_str = request.GET.get('start_date')  # дата начала из формы (если custom)
    end_date_str = request.GET.get('end_date')  # дата конца из формы

    # Стартовые значения до обработки
    start_date = default_start  # по умолчанию — первое число
    end_date = default_end  # по умолчанию — последнее число

    # Если переданы обе даты — парсим их как кастомный период
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()  # строка → дата
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            period = 'custom'  # меняем тип периода, чтобы отличать от week/month/year
        except ValueError:
            messages.error(request, "Неверный формат даты. Используйте формат ГГГГ-ММ-ДД.")
    elif period == 'week':
        start_date = today - timedelta(days=7)  # 7 дней назад
        end_date = today  # сегодня
    elif period == 'year':
        start_date = today.replace(month=1, day=1)  # 1 января
        end_date = today.replace(month=12, day=31)  # 31 декабря

    # Генерируем список всех дат периода
    delta = end_date - start_date  # количество дней в периоде
    all_dates = [start_date + timedelta(days=i) for i in range(delta.days + 1)]  # массив дат от start до end

    # === ДУБЛИРУЮЩАЯ ОБРАБОТКА ДАТ (исторический код — оставлен для совместимости) ===
    # Повторно читаем даты и перезаписываем start_date / end_date / all_dates
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()  # парсим кастомные даты
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            period = 'custom'
        except ValueError:
            messages.error(request, "Неверный формат даты. Используйте формат ГГГГ-ММ-ДД.")
            start_date = None  # сбрасываем даты — они будут переопределены ниже
            end_date = None
    else:
        today = date.today()  # текущая дата
        if period == 'week':
            start_date = today - timedelta(days=7)  # последние 7 дней
            end_date = today
        elif period == 'month':
            start_date = today.replace(day=1)  # первое число
            end_date = (today.replace(month=today.month + 1, day=1) - timedelta(days=1)) if today.month < 12 else today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)  # последнее число
        elif period == 'year':
            start_date = today.replace(month=1, day=1)  # 1 января
            end_date = today.replace(month=12, day=31)  # 31 декабря
        else:
            start_date = today.replace(day=1)  # первое число (fallback)
            end_date = (today.replace(month=today.month + 1, day=1) - timedelta(days=1)) if today.month < 12 else today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)

    # === НОРМАЛИЗАЦИЯ ПЕРИОДА ===
    # В форме скрытые start_date/end_date отправляются всегда, даже когда выбран week/month/year.
    # Поэтому учитываем их только если period=custom.
    today = date.today()
    period = request.GET.get('period', 'month')  # читаем период из формы
    start_date_str = request.GET.get('start_date')  # читаем дату начала
    end_date_str = request.GET.get('end_date')  # читаем дату конца

    if period == 'week':
        start_date = today - timedelta(days=7)  # неделя назад
        end_date = today  # сегодня
    elif period == 'year':
        start_date = today.replace(month=1, day=1)  # январь
        end_date = today.replace(month=12, day=31)  # декабрь
    elif period == 'custom':
        try:
            if not start_date_str or not end_date_str:
                raise ValueError("missing_custom_dates")  # не хватает дат
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()  # строка → дата
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            if start_date > end_date:
                start_date, end_date = end_date, start_date  # если даты перепутаны — меняем местами
        except ValueError:
            messages.error(request, "Для произвольного периода укажите корректные даты 'С' и 'По'.")
            period = 'month'  # откат к текущему месяцу
            start_date = today.replace(day=1)
            end_date = (today.replace(month=today.month + 1, day=1) - timedelta(days=1)) if today.month < 12 else today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        # month (по умолчанию)
        start_date = today.replace(day=1)  # первое число
        end_date = (today.replace(month=today.month + 1, day=1) - timedelta(days=1)) if today.month < 12 else today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)  # последнее число

    # Финальный список дат отчётного периода (перезаписываем поверх предыдущего)
    delta = end_date - start_date
    all_dates = [start_date + timedelta(days=i) for i in range(delta.days + 1)]

    # === ФИЛЬТРЫ МЕНЕДЖЕРА ===
    workout_id = request.GET.get('workout')  # фильтр по направлению (ID тренировки)
    search_query = request.GET.get('search', '').strip()  # поиск по имени/названию
    coverage_direction = request.GET.get('coverage_direction', 'all')  # фильтр покрытия направлений
    coverage_sort = request.GET.get('coverage_sort', 'trainers_desc')  # сортировка направлений

    # === ПРИМЕНЕНИЕ ФИЛЬТРОВ ===
    if is_manager:
        all_employees = UserProfile.objects.filter(role='employee').order_by('user__username')
        if employee_filter:
            employees = [employee_filter]  # только выбранный сотрудник
        else:
            employees = all_employees  # все сотрудники
    else:
        all_employees = [profile]  # сотрудник видит только себя
        employees = [profile]

    # === ЗАПРОС СМЕН (ShiftAssignment) ===
    # Берём все смены в выбранном диапазоне дат
    assignments_base = ShiftAssignment.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).select_related('employee', 'workout_type')  # подгружаем связанные записи (сотрудник и тип тренировки)
    assignments = assignments_base  # копия, к которой будем применять фильтры

    # Применяем фильтры к запросу смен
    if is_manager:
        if employee_filter:
            assignments = assignments.filter(employee=employee_filter)  # по сотруднику
        if workout_id and workout_id != 'all':
            assignments = assignments.filter(workout_type_id=workout_id)  # по направлению
        if search_query:
            assignments = assignments.filter(
                Q(employee__user__username__icontains=search_query) |
                Q(workout_type__name__icontains=search_query)
            )  # поиск по логину сотрудника или названию тренировки
    else:
        assignments = assignments.filter(employee=profile)  # только свои смены
        if workout_id and workout_id != 'all':
            assignments = assignments.filter(workout_type_id=workout_id)

    # === АГРЕГАЦИЯ ДАННЫХ ===
    # Загружаем историю ставок, которые действовали до конца периода
    period_end_moment = datetime.combine(end_date, datetime.max.time())
    if timezone.is_naive(period_end_moment):
        period_end_moment = timezone.make_aware(period_end_moment, timezone.get_current_timezone())
    # Список кортежей (effective_from, rate), отсортированных от новых к старым
    rate_changes = list(
        HourRateChange.objects.filter(effective_from__lte=period_end_moment)
        .order_by('-effective_from', '-id')
        .values_list('effective_from', 'rate')
    )
    rate_changes = [(dt, float(rate)) for dt, rate in rate_changes]

    from collections import defaultdict
    # data[employee_id][date] = часы за день (для табеля)
    data = defaultdict(lambda: defaultdict(float))
    emp_hours = defaultdict(float)  # total hours per employee
    emp_salary = defaultdict(float)  # total salary per employee
    day_hours = [0.0] * 7  # часы по дням недели (пн=0, вс=6)
    workout_hours = defaultdict(float)  # часы по направлениям
    date_hours = defaultdict(float)  # часы по календарным датам
    salary_available = False  # флаг: есть ли ставка для расчёта зарплаты

    # Проходим по каждой смене и суммируем часы/зарплату
    for a in assignments:
        if a.start_time is None or a.end_time is None:
            continue  # пропускаем смены без времени
        if not a.workout_type_id:
            continue  # пропускаем смены без направления
        # Длительность смены в часах (end_time - start_time)
        dur_raw = (datetime.combine(date.min, a.end_time) - datetime.combine(date.min, a.start_time)).total_seconds() / 3600
        dur = _round_half_up_to_int(dur_raw)  # округляем 0.5 вверх
        data[a.employee_id][a.date] += dur  # в табель
        emp_hours[a.employee.user.username] += dur  # в статистику по сотруднику
        day_hours[a.date.weekday()] += dur  # в статистику по дню недели
        workout_hours[a.workout_type.name] += dur  # в статистику по направлению
        date_hours[a.date] += dur  # в статистику по дате
        rate = _resolve_hour_rate_for_shift(a.date, a.start_time, rate_changes)  # ставка на момент смены
        if rate is not None:
            emp_salary[a.employee_id] += dur * rate  # зарплата = часы × ставка
            salary_available = True

    # Подсчёт итогов по каждому сотруднику
    total_hours = {}
    total_shifts = {}
    for emp in employees:
        emp_id = emp.id
        hours = sum(data[emp_id].values())
        shifts = sum(1 for v in data[emp_id].values() if v > 0)  # дни, когда были часы
        total_hours[emp.id] = int(round(hours))
        total_shifts[emp.id] = shifts

    # Итоги по дням (для табеля — строка "Итого по дням")
    daily_totals = []
    for d in all_dates:
        total = sum(data[emp.id].get(d, 0) for emp in employees)
        daily_totals.append(int(total))

    # Зарплата по каждому сотруднику
    total_salary_per_emp = {}
    for emp in employees:
        total_salary_per_emp[emp.id] = int(round(emp_salary.get(emp.id, 0)))

    # Общий фонд оплаты за период
    total_salary = int(round(sum(total_salary_per_emp.values())))

    # === ДАННЫЕ ДЛЯ ГРАФИКОВ (Chart.js) ===
    # Каждый ключ — это массив, который будет передан в JS как JSON
    chart_data = {
        'empNames': list(emp_hours.keys()) or [],  # имена сотрудников (ось X)
        'empValues': [int(round(v)) for v in emp_hours.values()] or [],  # часы сотрудников (ось Y)
        'dayLabels': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],  # дни недели для графика
        'dayValues': [int(round(v)) for v in day_hours] or [0]*7,  # часы по дням недели
        'workoutLabels': list(workout_hours.keys()) or [],  # названия направлений
        'workoutValues': [int(round(v)) for v in workout_hours.values()] or [],  # часы по направлениям
        'dateLabels': [d.strftime('%d.%m') for d in sorted(date_hours.keys())] or [],  # даты (ДД.ММ)
        'dateValues': [int(round(date_hours[d])) for d in sorted(date_hours.keys())] or [],  # часы по датам
    }

    # === АНАЛИТИКА ПО НАПРАВЛЕНИЯМ (только для менеджера) ===
    direction_rows = []
    employees_direction_rows = []
    direction_summary = {}
    workout_types_all = WorkoutType.objects.all().order_by('name')  # все типы тренировок
    staff_rows = []  # строки аналитики по персоналу
    staff_sort = request.GET.get('staff_sort', 'hours_desc')  # сортировка персонала
    staff_peak_filter = request.GET.get('staff_peak_day', 'all')  # фильтр по пиковому дню
    staff_swap_filter = request.GET.get('staff_swap_level', 'all')  # фильтр по частоте обменов
    staff_search_raw = request.GET.get('staff_search', '').strip()  # поиск по персоналу
    staff_search = staff_search_raw.lower()

    if is_manager:
        def _display_name(user_profile):
            # Собирает читаемое имя: Фамилия Имя или логин, если нет ФИО
            user_obj = user_profile.user  # получаем связанного пользователя (Person)
            full_name = f"{user_obj.last_name} {user_obj.first_name}".strip()  # склеиваем фамилию и имя
            return full_name if full_name else user_obj.username  # если пусто — возвращаем логин

        # Загружаем всех сотрудников с их направлениями (workout_types)
        all_employee_profiles = UserProfile.objects.filter(
            role='employee'  # только сотрудники (не менеджеры)
        ).select_related('user', 'employee_profile').prefetch_related('employee_profile__workout_types')  # подгружаем связанные модели

        # direction_to_trainers[workout_type_id] = список имён тренеров
        direction_to_trainers = {wt.id: [] for wt in workout_types_all}  # инициализируем пустыми списками
        employees_without_directions = []  # список сотрудников, у которых нет направлений

        for emp_profile in all_employee_profiles:
            emp_obj = getattr(emp_profile, 'employee_profile', None)  # EmployeeProfile (расширение с направлениями)
            if not emp_obj:
                continue  # у этого профиля нет EmployeeProfile — странный случай, пропускаем

            trainer_name = _display_name(emp_profile)
            trainer_workouts = list(emp_obj.workout_types.all())  # все направления, которые ведёт сотрудник

            if not trainer_workouts:
                employees_without_directions.append(trainer_name)  # сотрудник без направлений

            # Строка для таблицы "Направления сотрудников"
            employees_direction_rows.append({
                'name': trainer_name,  # имя тренера
                'workout_names': [w.name for w in trainer_workouts],  # список названий направлений
                'workout_count': len(trainer_workouts),  # количество направлений
            })

            # Добавляем тренера в список по каждому направлению
            for wt in trainer_workouts:
                direction_to_trainers.setdefault(wt.id, []).append(trainer_name)

        # Считаем нагрузку по направлениям (часы и количество смен)
        direction_assignments = assignments_base  # все смены за период (без фильтра по сотруднику)
        if employee_filter:
            direction_assignments = direction_assignments.filter(employee=employee_filter)  # если выбран конкретный сотрудник

        direction_hours = defaultdict(float)  # часы по workout_type_id
        direction_shifts = defaultdict(int)  # количество смен по workout_type_id
        for shift in direction_assignments:
            if not shift.workout_type_id:
                continue  # смена без типа тренировки — игнорируем
            if shift.start_time is None or shift.end_time is None:
                continue  # без времени начала/конца не можем посчитать длительность
            # Длительность в часах
            duration_raw = (datetime.combine(date.min, shift.end_time) - datetime.combine(date.min, shift.start_time)).total_seconds() / 3600
            duration = _round_half_up_to_int(duration_raw)
            direction_hours[shift.workout_type_id] += duration  # суммируем часы
            direction_shifts[shift.workout_type_id] += 1  # увеличиваем счётчик смен

        # Формируем строки таблицы направлений
        for wt in workout_types_all:
            if coverage_direction != 'all' and str(wt.id) != str(coverage_direction):
                continue  # если выбран конкретный фильтр — пропускаем остальные
            trainers = sorted(direction_to_trainers.get(wt.id, []))  # тренеры, отсортированные по алфавиту
            direction_rows.append({
                'id': wt.id,  # ID типа тренировки
                'name': wt.name,  # название направления
                'trainers': trainers,  # список тренеров (строкой)
                'trainers_count': len(trainers),  # сколько тренеров ведут это направление
                'hours': int(round(direction_hours.get(wt.id, 0))),  # суммарные часы за период
                'shifts': direction_shifts.get(wt.id, 0),  # количество смен
            })

        # Сортировка направлений по выбранному режиму
        if coverage_sort == 'trainers_asc':
            direction_rows.sort(key=lambda x: (x['trainers_count'], x['name'].lower()))  # по возрастанию числа тренеров
        elif coverage_sort == 'hours_desc':
            direction_rows.sort(key=lambda x: (-x['hours'], x['name'].lower()))  # по убыванию часов
        elif coverage_sort == 'hours_asc':
            direction_rows.sort(key=lambda x: (x['hours'], x['name'].lower()))  # по возрастанию часов
        elif coverage_sort == 'name_asc':
            direction_rows.sort(key=lambda x: x['name'].lower())  # по имени (А→Я)
        elif coverage_sort == 'name_desc':
            direction_rows.sort(key=lambda x: x['name'].lower(), reverse=True)  # по имени (Я→А)
        else:
            direction_rows.sort(key=lambda x: (-x['trainers_count'], x['name'].lower()))  # по умолчанию: от большего числа тренеров к меньшему

        # Сводка по направлениям (сколько всего, сколько покрыто тренерами, сколько нет)
        covered_count = len([r for r in direction_rows if r['trainers_count'] > 0])  # направления, у которых есть хотя бы 1 тренер
        direction_summary = {
            'total_directions': len(direction_rows),  # всего направлений
            'covered_directions': covered_count,  # обеспечены тренерами
            'uncovered_directions': len(direction_rows) - covered_count,  # нет ни одного тренера
            'employees_without_directions_count': len(employees_without_directions),  # сотрудники без привязки к направлениям
            'employees_without_directions': employees_without_directions,  # список таких сотрудников
        }

        # === АНАЛИТИКА ПО ПЕРСОНАЛУ ===
        weekday_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']  # для отображения пикового дня

        # Смены для расчёта статистики персонала
        assignments_for_staff = assignments_base  # базовый запрос (без дополнительных фильтров)
        if employee_filter:
            assignments_for_staff = assignments_for_staff.filter(employee=employee_filter)  # фильтр по сотруднику
        if workout_id and workout_id != 'all':
            assignments_for_staff = assignments_for_staff.filter(workout_type_id=workout_id)  # фильтр по направлению

        daily_hours_map = defaultdict(lambda: defaultdict(float))  # daily_hours_map[employee_id][date] = часы
        shifts_count_map = defaultdict(int)  # shifts_count_map[employee_id] = количество смен
        for shift in assignments_for_staff:
            if shift.start_time is None or shift.end_time is None:
                continue  # пропускаем смены без времени
            duration_raw = (datetime.combine(date.min, shift.end_time) - datetime.combine(date.min, shift.start_time)).total_seconds() / 3600
            duration = _round_half_up_to_int(duration_raw)
            daily_hours_map[shift.employee_id][shift.date] += duration  # суммируем часы за день
            shifts_count_map[shift.employee_id] += 1  # увеличиваем счётчик смен

        # Получаем все графики (Schedule), попадающие в период
        from ..models import Schedule, ScheduleApproval, ShiftSwapRequest  # импорт внутри функции (чтобы избежать циклического импорта)
        period_schedules = Schedule.objects.filter(
            start_date__lte=end_date,  # дата начала графика ≤ концу периода
            end_date__gte=start_date,  # дата конца графика ≥ началу периода
        )

        # Согласования графиков (одобрение / отказ сотрудниками)
        approvals_qs = ScheduleApproval.objects.filter(
            schedule__in=period_schedules  # только для графиков, попадающих в период
        ).exclude(approved__isnull=True)  # только те, на которые ответили (не NULL)
        approvals_qs = approvals_qs.select_related('employee')

        approval_map = defaultdict(lambda: {'responded': 0, 'rejected': 0})  # {employee_id: ответы}
        for approval in approvals_qs:
            approval_map[approval.employee_id]['responded'] += 1  # ответил (согласился или отказался)
            if approval.approved is False:
                approval_map[approval.employee_id]['rejected'] += 1  # отказался

        # Обмены сменами за период (только завершённые или утверждённые)
        swap_qs = ShiftSwapRequest.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            status__in=['approved_by_manager', 'completed']  # только успешные обмены
        ).select_related('from_employee__user_profile', 'to_employee__user_profile')

        swap_involved_map = defaultdict(int)  # сколько раз сотрудник участвовал в обмене (отправил + получил)
        swap_sent_map = defaultdict(int)  # сколько раз сотрудник отправил смену (был from_employee)
        swap_received_map = defaultdict(int)  # сколько раз сотрудник получил смену (был to_employee)
        for swap in swap_qs:
            from_profile_id = swap.from_employee.user_profile_id if swap.from_employee_id else None
            to_profile_id = swap.to_employee.user_profile_id if swap.to_employee_id else None
            if from_profile_id:
                swap_involved_map[from_profile_id] += 1  # сотрудник участвовал как отправитель
                swap_sent_map[from_profile_id] += 1  # отправил смену
            if to_profile_id:
                swap_involved_map[to_profile_id] += 1  # сотрудник участвовал как получатель
                swap_received_map[to_profile_id] += 1

        # Собираем строки таблицы аналитики по сотрудникам
        for emp_profile in all_employee_profiles:
            emp_id = emp_profile.id  # ID сотрудника (UserProfile.id)
            full_name = _display_name(emp_profile)  # читаемое имя
            login_name = emp_profile.user.username  # логин в системе

            daily_items = daily_hours_map.get(emp_id, {})  # словарь {дата: часы} для этого сотрудника
            total_hours_emp = round(sum(daily_items.values()), 2)  # всего часов за период
            shifts_emp = shifts_count_map.get(emp_id, 0)  # количество смен
            worked_days = [h for h in daily_items.values() if h > 0]  # фильтр: только дни, где были часы
            worked_days_count = len(worked_days)  # количество рабочих дней
            avg_per_workday = round(total_hours_emp / worked_days_count, 2) if worked_days_count else 0.0  # среднее часов за рабочий день

            # Равномерность нагрузки: коэффициент вариации → балл от 0 до 100
            if worked_days_count >= 2:
                mean_val = statistics.mean(worked_days)  # среднее часов за день
                std_val = statistics.pstdev(worked_days)  # стандартное отклонение
                cv = (std_val / mean_val) if mean_val > 0 else 1.0  # коэффициент вариации
                uniformity_score = max(0, round(100 - min(100, cv * 100), 1))  # 100 = идеально равномерно
            elif worked_days_count == 1:
                uniformity_score = 100.0  # один день — равномерность 100%
            else:
                uniformity_score = 0.0  # нет смен — равномерность 0

            # Пиковый день недели (с максимальной нагрузкой)
            peak_day_name = '—'  # значение по умолчанию (нет пикового дня)
            if daily_items:
                peak_day_index, _ = max(
                    ((d.weekday(), hrs) for d, hrs in daily_items.items()),  # пары (день_недели, часы)
                    key=lambda pair: pair[1]  # выбираем с максимальными часами
                )
                peak_day_name = weekday_names[peak_day_index]  # переводим индекс в название (Пн, Вт...)

            approved_swaps = swap_involved_map.get(emp_id, 0)  # всего обменов (отправил + получил)
            swaps_sent = swap_sent_map.get(emp_id, 0)  # сколько раз отправил
            swaps_received = swap_received_map.get(emp_id, 0)  # сколько раз получил
            swap_frequency_pct = round((approved_swaps / shifts_emp) * 100, 1) if shifts_emp else 0.0  # % смен, участвовавших в обмене

            responded = approval_map[emp_id]['responded']  # сколько раз ответил на график
            rejected = approval_map[emp_id]['rejected']  # сколько раз отказался
            rejection_pct = round((rejected / responded) * 100, 1) if responded else 0.0  # % отказов

            staff_rows.append({
                'employee_id': emp_id,  # ID сотрудника
                'name': full_name,  # Фамилия Имя
                'username': login_name,  # логин
                'hours': total_hours_emp,  # всего часов
                'worked_days': worked_days_count,  # рабочих дней
                'avg_per_day': avg_per_workday,  # среднее часов за день
                'uniformity': uniformity_score,  # равномерность (0-100)
                'rejection_pct': rejection_pct,  # % отказов согласования
                'rejected_count': rejected,  # сколько раз отказал
                'responded_count': responded,  # сколько раз ответил
                'swap_count': approved_swaps,  # всего обменов
                'swap_sent': swaps_sent,  # отправил
                'swap_received': swaps_received,  # получил
                'swap_frequency': swap_frequency_pct,  # частота обменов (в %)
                'peak_day': peak_day_name,  # пиковый день недели
            })

        # Применяем фильтры к персоналу
        if staff_peak_filter != 'all':
            staff_rows = [row for row in staff_rows if row['peak_day'] == staff_peak_filter]  # фильтр по пиковому дню

        if staff_swap_filter == 'none':
            staff_rows = [row for row in staff_rows if row['swap_count'] == 0]  # без обменов
        elif staff_swap_filter == 'low':
            staff_rows = [row for row in staff_rows if 0 < row['swap_frequency'] <= 20]  # низкая частота обменов
        elif staff_swap_filter == 'high':
            staff_rows = [row for row in staff_rows if row['swap_frequency'] > 20]  # высокая частота обменов

        # Поиск по имени или логину
        if staff_search:
            staff_rows = [row for row in staff_rows if staff_search in row['name'].lower() or staff_search in row['username'].lower()]

        # Сортировка персонала по выбранному режиму
        if staff_sort == 'hours_asc':
            staff_rows.sort(key=lambda x: (x['hours'], x['name'].lower()))  # по возрастанию часов
        elif staff_sort == 'uniformity_desc':
            staff_rows.sort(key=lambda x: (-x['uniformity'], x['name'].lower()))  # по убыванию равномерности
        elif staff_sort == 'uniformity_asc':
            staff_rows.sort(key=lambda x: (x['uniformity'], x['name'].lower()))  # по возрастанию равномерности
        elif staff_sort == 'reject_desc':
            staff_rows.sort(key=lambda x: (-x['rejection_pct'], x['name'].lower()))  # по убыванию отказов
        elif staff_sort == 'swap_desc':
            staff_rows.sort(key=lambda x: (-x['swap_count'], x['name'].lower()))  # по убыванию обменов
        elif staff_sort == 'name_asc':
            staff_rows.sort(key=lambda x: x['name'].lower())  # по имени (А→Я)
        else:
            staff_rows.sort(key=lambda x: (-x['hours'], x['name'].lower()))  # по умолчанию: от большего числа часов к меньшему

    # Данные для графика персонала (топ-12 сотрудников по часам)
    staff_chart = {
        'labels': [row['name'] for row in staff_rows[:12]],  # имена (не более 12)
        'hours': [row['hours'] for row in staff_rows[:12]],  # часы для графика
        'uniformity': [row['uniformity'] for row in staff_rows[:12]],  # равномерность
        'rejection': [row['rejection_pct'] for row in staff_rows[:12]],  # % отказов
        'swaps': [row['swap_count'] for row in staff_rows[:12]],  # количество обменов
    }

    # Сводка по персоналу (суммарные показатели)
    staff_summary = {
        'trainers_count': len(staff_rows),  # количество тренеров
        'total_hours': round(sum((row.get('hours') or 0) for row in staff_rows), 1),  # суммарные часы
        'avg_uniformity': round((sum((row.get('uniformity') or 0) for row in staff_rows) / len(staff_rows)), 1) if staff_rows else 0.0,  # средняя равномерность
        'avg_rejection_pct': round((sum((row.get('rejection_pct') or 0) for row in staff_rows) / len(staff_rows)), 1) if staff_rows else 0.0,  # средний % отказов
        'total_swaps': int(sum((row.get('swap_count') or 0) for row in staff_rows)),  # всего обменов
    }

    # === СБОРКА КОНТЕКСТА ДЛЯ ШАБЛОНА ===
    # Все эти переменные будут доступны в reports.html как {{ переменная }}
    context = {
        'start_date': start_date,  # начало периода
        'end_date': end_date,  # конец периода
        'period': period,  # week / month / year / custom
        'employee_id': getattr(employee_filter, 'id', 'all') if is_manager else 'self',  # выбранный сотрудник
        'workout_id': workout_id or 'all',  # выбранное направление
        'search_query': search_query,  # строка поиска
        'employees': employees,  # список сотрудников для табеля
        'all_employees': all_employees if is_manager else [],  # все сотрудники (для менеджера)
        'workout_types': WorkoutType.objects.all(),  # все типы тренировок (для фильтра)
        'all_dates': all_dates,  # массив дат периода (для шапки табеля)
        'data': data,  # табель: [employee_id][date] = часы
        'total_hours': total_hours,  # итого часов по сотрудникам
        'total_shifts': total_shifts,  # итого смен по сотрудникам
        'daily_totals': daily_totals,  # итоги по дням
        'total_all_hours': int(round(sum(total_hours.values()))),  # всего часов за период
        'total_all_assignments': assignments.count(),  # всего смен за период
        'active_employees': len(employees),  # количество сотрудников в табеле
        'chart_data_json': json.dumps(chart_data, ensure_ascii=False),  # данные для графиков (JSON для Chart.js)
        'hour_rate': hour_rate,  # текущая часовая ставка
        'rate_last_changed_at': latest_rate.created_at if latest_rate else None,  # дата последнего изменения ставки
        'total_salary': total_salary,  # общий ФОТ за период
        'total_salary_per_emp': total_salary_per_emp,  # зарплата по каждому сотруднику
        'salary_available': salary_available,  # флаг: показывать колонку ЗП (True если есть ставка)
        'is_manager': is_manager,  # флаг: текущий пользователь — менеджер
        'coverage_direction': coverage_direction,  # фильтр по направлению (покрытие)
        'coverage_sort': coverage_sort,  # сортировка направлений
        'direction_rows': direction_rows,  # строки таблицы покрытия направлений
        'employees_direction_rows': employees_direction_rows,  # строки таблицы "Направления сотрудников"
        'direction_summary': direction_summary,  # сводка по направлениям
        'staff_rows': staff_rows,  # строки аналитики по персоналу
        'staff_sort': staff_sort,  # режим сортировки персонала
        'staff_peak_filter': staff_peak_filter,  # фильтр по пиковому дню
        'staff_swap_filter': staff_swap_filter,  # фильтр по частоте обменов
        'staff_search': staff_search_raw,  # поиск по персоналу (оригинальный текст)
        'staff_chart_json': json.dumps(staff_chart, ensure_ascii=False),  # данные графика персонала (JSON)
        'staff_summary': staff_summary,  # сводка по персоналу
    }
    return render(request, 'core/reports/reports.html', context)  # рендерим шаблон с контекстом
