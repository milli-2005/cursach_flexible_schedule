"""
Страница и API-обработчики правил распределения занятий при автозаполнении графика.

Архитектура:
  Правила распределения — это ограничения вида «Табата не чаще 1 раза утром и 1 раза
  вечером в неделю». Они создаются менеджером на странице /schedules/rules/ через
  ИИ-распознавание (ввод текста → парсинг → сохранение).

  После сохранения правила живут в БД (DistributionRule). При создании графика
  (create_schedule_view) все активные правила сериализуются в JS-константу
  ACTIVE_DISTRIBUTION_RULES. Алгоритм автозаполнения проверяет каждое правило
  в браузере при подборе тренера в ячейку.

  Этот файл содержит:
  1. _generate_studio_slots — утилита для генерации временных слотов (общая)
  2. _parse_distribution_rule_text — fallback-парсер (без ИИ) для простых фраз
  3. _serialize_active_distribution_rules — сериализация для JS
  4. Конфликты: _extract_*_signature, _build_distribution_rules_conflicts
  5. Страница: distribution_rules_page
  6. API: parse / save / toggle / delete / update / test
"""

# Импортируем модуль для работы с регулярными выражениями
import re
# Импортируем AI-парсер, который пробует распознать правило через нейросеть
from ..services.rule_ai_parser import try_parse_rule_with_ai
# Импортируем все декораторы и утилиты аутентификации (login_required, user_passes_test, is_manager и т.д.)
from .auth import *

# ═══════════════════════════════════════════════════════════
# Константы студийных слотов (9:00–21:00, обед 14:00–16:00)
# ═══════════════════════════════════════════════════════════
# Студия работает с 9 до 21. Одно занятие = 50 мин + 10 мин перерыв.
# Обеденный перерыв 14:00–16:00 — в это время слоты не создаются.
# Время начала рабочего дня студии — 9:00 (в минутах от полуночи)
STUDIO_DAY_START_MIN = 9 * 60    # 09:00 в минутах
# Время окончания рабочего дня студии — 21:00 (в минутах от полуночи)
STUDIO_DAY_END_MIN = 21 * 60     # 21:00 в минутах
# Длительность одного занятия — 50 минут
SLOT_WORK_MIN = 50               # Длительность занятия
# Длительность перерыва между занятиями — 10 минут
SLOT_BREAK_MIN = 10              # Перерыв между занятиями
# Время начала обеденного перерыва — 14:00 (в минутах от полуночи)
STUDIO_LUNCH_START_MIN = 14 * 60 # Начало обеда
# Время окончания обеденного перерыва — 16:00 (в минутах от полуночи)
STUDIO_LUNCH_END_MIN = 16 * 60   # Конец обеда


def _generate_studio_slots():
    """
    Генерирует временные слоты для расписания.

    Возвращает список кортежей (start_str, end_str), например:
    [('09:00', '09:50'), ('10:00', '10:50'), ..., ('20:00', '20:50')]

    Обед 14:00–16:00 пропускается — слотов в это время нет.
    Используется в create_schedule_view, edit_schedule_view, schedule_detail.
    """
    # Создаём пустой список для хранения слотов
    slots = []
    # Устанавливаем текущее время на начало рабочего дня (9:00)
    current_time = STUDIO_DAY_START_MIN
    # Цикл: пока текущее время + длительность занятия укладывается в рабочий день
    while current_time + SLOT_WORK_MIN <= STUDIO_DAY_END_MIN:
        # Время начала текущего слота
        start_min = current_time
        # Время окончания текущего слота (начало + длительность)
        end_min = current_time + SLOT_WORK_MIN
        # Проверяем, попадает ли слот на обед (целиком или частично)
        intersects_lunch = start_min < STUDIO_LUNCH_END_MIN and end_min > STUDIO_LUNCH_START_MIN
        # Если слот не пересекается с обедом — добавляем его в список
        if not intersects_lunch:
            # Форматируем время начала в строку вида "ЧЧ:ММ"
            start_str = f"{start_min // 60:02d}:{start_min % 60:02d}"
            # Форматируем время окончания в строку вида "ЧЧ:ММ"
            end_str = f"{end_min // 60:02d}:{end_min % 60:02d}"
            # Добавляем кортеж (начало, конец) в список слотов
            slots.append((start_str, end_str))
        # Сдвигаемся на длину слота + перерыв для следующей итерации
        current_time = end_min + SLOT_BREAK_MIN
    # Возвращаем готовый список временных слотов
    return slots


# ═══════════════════════════════════════════════════════════
# Fallback-парсер (без ИИ)
# ═══════════════════════════════════════════════════════════
# Если ИИ недоступен (нет ключа или ошибка), подключается этот парсер.
# Он ищет ключевые слова в тексте и сопоставляет их с шаблонами.
# Поддерживает ~10 популярных формулировок на русском.
# Словарь для перевода русских названий дней недели в индексы (0=пн ... 6=вс)
DAY_NAME_TO_INDEX = {
    # Понедельник: полное и сокращённое название
    'понедельник': 0, 'пн': 0,
    # Вторник: полное и сокращённое название
    'вторник': 1, 'вт': 1,
    # Среда: полное и сокращённое название
    'среда': 2, 'ср': 2,
    # Четверг: полное и сокращённое название
    'четверг': 3, 'чт': 3,
    # Пятница: полное и сокращённое название
    'пятница': 4, 'пт': 4,
    # Суббота: полное и сокращённое название
    'суббота': 5, 'сб': 5,
    # Воскресенье: полное и сокращённое название
    'воскресенье': 6, 'вс': 6,
}


def _normalize_rule_text(text: str) -> str:
    """Приводит текст к нижнему регистру и схлопывает лишние пробелы."""
    # Если text None или пустая строка — заменяем на пустую строку; обрезаем края; приводим к нижнему регистру; заменяем множественные пробелы на один
    return re.sub(r'\s+', ' ', (text or '').strip().lower())


# Соответствие русских названий занятий английским категориям (для выбора bucket в алгоритме)
# Ключ — подстрока, которая может быть в тексте правила; значение — категория
WORKOUT_CATEGORY_ALIASES = {
    # Спокойные тренировки: русские и английские варианты
    'спокойн': 'calm',
    'calm': 'calm',
    'йог': 'calm',
    'стретч': 'calm',
    'растяж': 'calm',
    'пилатес': 'calm',
    # Кардио-тренировки: русские и английские варианты
    'кардио': 'cardio',
    'cardio': 'cardio',
    'табат': 'cardio',
    'hiit': 'cardio',
    # Силовые тренировки: русские и английские варианты
    'силов': 'strength',
    'strength': 'strength',
    'power': 'strength',
    # Танцевальные тренировки: русские и английские варианты
    'танц': 'dance',
    'dance': 'dance',
    'бачата': 'dance',
    'стрип': 'dance',
    'восточ': 'dance',
}


def _extract_category_from_text(src: str):
    """Проверяет, есть ли в тексте слово-маркер категории (йога=calm, табата=cardio и т.д.)."""
    # Перебираем все ключи (подстроки) в словаре алиасов
    for key, value in WORKOUT_CATEGORY_ALIASES.items():
        # Если ключ найден в исходном тексте — возвращаем соответствующую категорию
        if key in src:
            return value
    # Если ничего не нашли — возвращаем None
    return None

def _extract_categories_from_text(src: str):
    """Возвращает список ВСЕХ категорий, найденных в тексте, в порядке упоминания."""
    # Создаём пустой список для хранения найденных совпадений
    matches = []
    # Перебираем все ключи (подстроки) в словаре алиасов
    for key, value in WORKOUT_CATEGORY_ALIASES.items():
        # Ищем позицию ключа в исходном тексте
        pos = src.find(key)
        # Если ключ найден, и такой категории ещё нет в списке — добавляем
        if pos != -1 and value not in [m[1] for m in matches]:
            # Запоминаем позицию и название категории
            matches.append((pos, value))
    # Сортируем совпадения по позиции в тексте (порядок упоминания)
    matches.sort(key=lambda x: x[0])
    # Возвращаем только названия категорий (без позиций)
    return [m[1] for m in matches]


def _parse_distribution_rule_text(text: str):
    """
    Парсит текст правила без ИИ, только по шаблонам.

    Каждый шаблон — это регулярное выражение, которое ищет ключевые слова
    (утро/вечер/неделя/подряд/чередование) и извлекает числа-ограничения.

    Возвращает (payload_dict, None) при успехе или (None, error_string) при ошибке.
    """
    # Нормализуем исходный текст: нижний регистр, схлопывание пробелов
    src = _normalize_rule_text(text)
    # Если после нормализации текст пустой — возвращаем ошибку
    if not src:
        return None, 'Введите текст правила.'

    # ── Шаблон 1: «Табата не более 1 раза утром и 1 раза вечером в неделю» ──
    # Ищет: "что-то не более/только N раз утром M раз вечером в неделю"
    weekly_pattern = re.search(
        # Регулярное выражение: группа target — название тренировки, далее "не более" или "только", число для утра, число для вечера, "недел"
        r'(?P<target>[а-яa-z0-9 \-_]+?)\s+.*?(?:не более|только)\s+(?P<morning>\d+)\s+раз.*?утр.*?(?P<evening>\d+)\s+раз.*?вечер.*?недел',
        src
    )
    # Если шаблон найден — разбираем результат
    if weekly_pattern:
        # Извлекаем название тренировки (цель ограничения) и обрезаем кавычки/пробелы
        raw_target = weekly_pattern.group('target').strip(' "«»')
        # Пытаемся определить категорию по названию (например, табата → cardio)
        target_category = _extract_category_from_text(raw_target)
        # Извлекаем максимальное количество для утреннего окна
        morning_max = int(weekly_pattern.group('morning'))
        # Извлекаем максимальное количество для вечернего окна
        evening_max = int(weekly_pattern.group('evening'))
        # Формируем параметры правила: период — неделя, два временных окна с лимитами
        params = {
            'period': 'week',
            'buckets': [
                # Утреннее окно: с 9:00 до 14:00, лимит morning_max
                {'name': 'morning', 'start': '09:00', 'end': '14:00', 'max': morning_max},
                # Вечернее окно: с 16:00 до 21:00, лимит evening_max
                {'name': 'evening', 'start': '16:00', 'end': '21:00', 'max': evening_max},
            ],
        }
        # Определяем, является ли цель broad-категорией или конкретной тренировкой
        normalized_name = _normalize_workout_name_for_rule(raw_target)
        # Если нормализованное имя совпадает с названием категории («кардио»→«cardio» → категория,
        # «табата»→«tabata»≠«cardio» → конкретная тренировка)
        is_category_keyword = target_category and normalized_name == target_category
        if is_category_keyword:
            # Используем режим цели "category"
            params.update({'target_mode': 'category', 'category': target_category})
            title = f'Лимит категории "{target_category}" по неделе'
        else:
            # Используем режим цели "workout" с названием тренировки
            params.update({'target_mode': 'workout', 'workout_name': normalized_name})
            title = f'Лимит "{normalized_name}" по неделе'
        # Формируем payload — структуру правила для сохранения
        payload = {
            'rule_type': 'weekly_limit',
            'severity': 'hard',
            'name': title,
            'params_json': params
        }
        # Возвращаем успешный результат (payload, без ошибки)
        return payload, None

    # ── Шаблон 1.1: «табата только 2 раза в неделю» / «не более 2 раз в неделю» ──
    total_week_pattern = re.search(
        # Регулярное выражение: группа target — название, "только" или "не более", число, "раз", "недел"
        r'(?P<target>[а-яa-z0-9 \-_]+?)\s+.*?(?:только|не более)\s+(?P<count>\d+)\s+раз\w*\s+.*?недел',
        src
    )
    # Если шаблон найден — разбираем результат
    if total_week_pattern:
        # Извлекаем название тренировки и обрезаем кавычки
        raw_target = total_week_pattern.group('target').strip(' "«»')
        # Пытаемся определить категорию по названию
        target_category = _extract_category_from_text(raw_target)
        # Извлекаем общий лимит на неделю
        total_max = int(total_week_pattern.group('count'))
        # Формируем параметры: период — неделя, максимальное количество
        params = {'period': 'week', 'max_total': total_max}
        # Определяем, является ли цель broad-категорией или конкретной тренировкой
        normalized_name = _normalize_workout_name_for_rule(raw_target)
        is_category_keyword = target_category and normalized_name == target_category
        if is_category_keyword:
            params.update({'target_mode': 'category', 'category': target_category})
            title = f'Лимит категории "{target_category}" за неделю'
        else:
            normalized_name = _normalize_workout_name_for_rule(raw_target)
            params.update({'target_mode': 'workout', 'workout_name': normalized_name})
            title = f'Лимит "{normalized_name}" за неделю'
        # Формируем payload правила
        payload = {
            'rule_type': 'weekly_limit',
            'severity': 'hard',
            'name': title,
            'params_json': params
        }
        # Возвращаем успешный результат
        return payload, None

    # ── Шаблон 1.2: «две одинаковые тренировки в один день нельзя» ──
    # Проверяем, содержит ли текст слова "одинаков" или "дубликат"
    duplicate_day_pattern = (
        ('одинаков' in src or 'дубликат' in src) and
        # И при этом слова "один день", "в один день" или "за день"
        ('один день' in src or 'в один день' in src or 'за день' in src) and
        # И при этом слова "нельзя", "запрет" или "не став"
        ('нельзя' in src or 'запрет' in src or 'не став' in src)
    )
    # Если все условия совпали — формируем правило
    if duplicate_day_pattern:
        # Формируем payload: тип — запрет дублей за день
        payload = {
            'rule_type': 'daily_duplicate_limit',
            'severity': 'hard',
            'name': 'Запрет одинаковых тренировок в день (утро/вечер)',
            'params_json': {
                # Проверка в разрезе временного окна (утро/вечер)
                'scope': 'bucket',
                # Максимум — 1 одинаковой тренировки в окне
                'max_per_bucket_per_day': 1,
                # Определяем два временных окна: утро и вечер
                'buckets': [
                    {'name': 'morning', 'start': '09:00', 'end': '14:00'},
                    {'name': 'evening', 'start': '16:00', 'end': '21:00'},
                ],
            }
        }
        # Возвращаем успешный результат
        return payload, None

    # ── Шаблон 2: «по понедельникам и средам можно 2 спокойные подряд» ──
    # Проверяем, есть ли в тексте "спокойн", "подряд" и один из дней
    if 'спокойн' in src and 'подряд' in src and ('понедель' in src or 'сред' in src):
        # Создаём пустой список для найденных дней недели
        weekdays = []
        # Перебираем словарь названий дней недели
        for key, value in DAY_NAME_TO_INDEX.items():
            # Если ключ найден в тексте и такого индекса ещё нет — добавляем
            if key in src and value not in weekdays:
                weekdays.append(value)
        # Если дни не удалось распознать — ставим понедельник и среду по умолчанию
        if not weekdays:
            weekdays = [0, 2]  # если дни не распознались — ставим пн и ср
        # Формируем payload правила
        payload = {
            'rule_type': 'calm_consecutive',
            'severity': 'hard',
            'name': 'Спокойные подряд в выбранные дни',
            'params_json': {
                # Сортируем дни и убираем дубликаты
                'weekdays': sorted(set(weekdays)),
                # Максимум 2 спокойных тренировки подряд
                'max_consecutive': 2,
                # Категория — calm (спокойные)
                'category': 'calm',
            }
        }
        # Возвращаем успешный результат
        return payload, None

    # ── Шаблон 2.2: «по понедельникам и средам нужно больше спокойных» ──
    if ('спокойн' in src or 'спокой' in src) and 'больше' in src and ('понедель' in src or 'сред' in src or 'вторник' in src or 'четверг' in src or 'пятниц' in src or 'суббот' in src or 'воскрес' in src):
        weekdays = []
        for key, value in DAY_NAME_TO_INDEX.items():
            if key in src and value not in weekdays:
                weekdays.append(value)
        if not weekdays:
            weekdays = [0, 2]
        payload = {
            'rule_type': 'calm_consecutive',
            'severity': 'soft',
            'name': 'Больше спокойных в выбранные дни',
            'params_json': {
                'weekdays': sorted(set(weekdays)),
                'max_consecutive': 3,
                'category': 'calm',
            }
        }
        return payload, None

    # ── Шаблон 2.1: «не ставь несколько силовых подряд» ──
    # Проверяем, есть ли в тексте "силов" и "подряд"
    if 'силов' in src and 'подряд' in src:
        # Формируем payload: запрет силовых подряд
        payload = {
            'rule_type': 'calm_consecutive',
            'severity': 'hard',
            'name': 'Запрет нескольких силовых подряд',
            'params_json': {
                # Применяется ко всем дням недели
                'weekdays': [0, 1, 2, 3, 4, 5, 6],
                # Максимум — 1 силовая подряд (т.е. нельзя ставить две подряд)
                'max_consecutive': 1,
                # Категория — strength (силовые)
                'category': 'strength',
            }
        }
        # Возвращаем успешный результат
        return payload, None

    # ── Шаблон 3: чередование (извлекаем категории из текста) ──
    # Проверяем, есть ли в тексте корень "черед"
    if 'черед' in src:
        # Извлекаем все категории, упомянутые в тексте, в порядке появления
        cats = _extract_categories_from_text(src)
        # Если найдено 2 или более категорий — формируем правило
        if len(cats) >= 2:
            # Склеиваем названия категорий для отображения
            cat_display = ', '.join(cats)
            # Формируем payload: чередование категорий
            payload = {
                'rule_type': 'alternation',
                'severity': 'hard',
                'name': f'Чередование {cat_display}',
                'params_json': {
                    # Применяется ко всем дням недели
                    'weekdays': [0, 1, 2, 3, 4, 5, 6],
                    # Список категорий для чередования
                    'categories': cats,
                    # Режим — строгое чередование (каждая следующая должна отличаться)
                    'mode': 'strict_alternate',
                }
            }
            # Возвращаем успешный результат
            return payload, None

    # ── Шаблон 4: «не ставь две силовые подряд» ──
    # Проверяем наличие слов "силов"/"спокой" + "подряд" + "не"/"запрет"
    if ('силов' in src or 'спокой' in src) and 'подряд' in src and ('не' in src or 'запрет' in src):
        # Определяем категорию: если есть "силов" — strength, иначе calm
        cat = 'strength' if 'силов' in src else 'calm'
        # Формируем payload: запрет нескольких подряд
        payload = {
            'rule_type': 'calm_consecutive',
            'severity': 'hard',
            'name': f'Запрет нескольких {cat} подряд',
            'params_json': {
                # Применяется ко всем дням недели
                'weekdays': [0, 1, 2, 3, 4, 5, 6],
                # Максимум — 1 (нельзя ставить одну и ту же категорию дважды подряд)
                'max_consecutive': 1,
                # Категория, к которой применяется ограничение
                'category': cat,
            }
        }
        # Возвращаем успешный результат
        return payload, None

    # ── Шаблон 5: «не более N раз в день» / «не чаще N раз в день» ──
    daily_limit = re.search(
        # Регулярное выражение: название, "не более" или "не чаще", число, "раз", "ден"
        r'(?P<target>[а-яa-z0-9 \-_]+?)\s+.*?(?:не более|не чаще)\s+(?P<count>\d+)\s+раз.*?ден',
        src
    )
    # Если шаблон найден — разбираем результат
    if daily_limit:
        # Извлекаем название тренировки и обрезаем кавычки
        raw_target = daily_limit.group('target').strip(' "«»')
        # Извлекаем максимальное количество раз в день
        count = int(daily_limit.group('count'))
        # Формируем payload: лимит на день
        payload = {
            'rule_type': 'daily_duplicate_limit',
            'severity': 'hard',
            'name': f'Лимит {raw_target}: {count} в день',
            'params_json': {
                # Глобальная проверка — на весь день, а не по окнам
                'scope': 'global',
                # Максимум повторений одной тренировки в день
                'max_per_bucket_per_day': count,
                # Два временных окна: утро и вечер
                'buckets': [
                    {'name': 'morning', 'start': '09:00', 'end': '14:00'},
                    {'name': 'evening', 'start': '16:00', 'end': '21:00'},
                ],
            }
        }
        # Возвращаем успешный результат
        return payload, None

    # ── Шаблон 6: «утром не более N» (только утро, без вечера) ──
    morning_only = re.search(
        # Регулярное выражение: название, "утр", "не более" или "только", число
        r'(?P<target>[а-яa-z0-9 \-_]+?)\s+.*?утр.*?(?:не более|только)\s+(?P<count>\d+)',
        src
    )
    # Если шаблон найден — разбираем результат
    if morning_only:
        # Извлекаем название тренировки и обрезаем кавычки
        raw_target = morning_only.group('target').strip(' "«»')
        # Извлекаем максимальное количество для утра
        count = int(morning_only.group('count'))
        # Пытаемся определить категорию по названию
        target_category = _extract_category_from_text(raw_target)
        # Формируем параметры: только утреннее окно
        params = {
            'period': 'week',
            'buckets': [
                # Только утреннее окно с 9:00 до 14:00 с лимитом count
                {'name': 'morning', 'start': '09:00', 'end': '14:00', 'max': count},
            ],
        }
        # Определяем, является ли цель broad-категорией или конкретной тренировкой
        normalized_name = _normalize_workout_name_for_rule(raw_target)
        is_category_keyword = target_category and normalized_name == target_category
        if is_category_keyword:
            params.update({'target_mode': 'category', 'category': target_category})
            title = f'Лимит категории "{target_category}" утром'
        else:
            params.update({'target_mode': 'workout', 'workout_name': normalized_name})
            title = f'Лимит "{normalized_name}" утром'
        # Формируем payload правила
        payload = {
            'rule_type': 'weekly_limit',
            'severity': 'hard',
            'name': title,
            'params_json': params
        }
        # Возвращаем успешный результат
        return payload, None

    # ── Шаблон 7: «одинаковые тренировки не повторяются за смену» ──
    # Проверяем, есть ли слова "одинаков"/"повтор" и "трениров"/"занят"
    if ('одинаков' in src or 'повтор' in src) and ('трениров' in src or 'занят' in src):
        # Формируем payload: запрет одинаковых за смену
        payload = {
            'rule_type': 'daily_duplicate_limit',
            'severity': 'hard',
            'name': 'Запрет одинаковых тренировок за смену',
            'params_json': {
                # Проверка в разрезе тренера
                'scope': 'trainer',
                # Максимум — 1 (одинаковая тренировка не должна повторяться)
                'max_per_bucket_per_day': 1,
                # Одно окно на весь день с 9:00 до 21:00
                'buckets': [
                    {'name': 'full_day', 'start': '09:00', 'end': '21:00'},
                ],
            }
        }
        # Возвращаем успешный результат
        return payload, None

    # ── Шаблон 8: «не ставь N одинаковых категорий подряд» ──
    cat_consecutive = re.search(
        # Регулярное выражение: запрет, число, "одинаковых", "категор"
        # Между запретом и числом могут быть любые слова (ставь/ставить/ставить/повторять/...)
        r'(?:не\s+став|запрещ|запрет|нельзя).*?(?P<count>\d+)\s+одинаковы[ех]\s+категор',
        src
    )
    # Если шаблон найден — разбираем результат
    if cat_consecutive:
        # Извлекаем количество одинаковых категорий, которые нельзя ставить
        count = int(cat_consecutive.group('count'))
        # Формируем payload: запрет одинаковых категорий подряд
        payload = {
            'rule_type': 'daily_duplicate_limit',
            'severity': 'hard',
            'name': f'Запрет одинаковых категорий подряд (не более {count - 1})',
            'params_json': {
                # Проверка в разрезе тренера
                'scope': 'trainer',
                # Максимум — count - 1 (т.е. если count=2, то не более 1)
                'max_per_bucket_per_day': count - 1,
                # Одно окно на весь день с 9:00 до 21:00
                'buckets': [
                    {'name': 'full_day', 'start': '09:00', 'end': '21:00'},
                ],
            }
        }
        # Возвращаем успешный результат
        return payload, None

    # ── Шаблон 9: «максимум N вида танцев за вечер/утро/день» ──
    if 'максимум' in src and 'вид' in src:
        daily_cat = re.search(r'(?P<count>\d+)\s+вид\S*', src)
        if daily_cat and ('вечер' in src or 'утро' in src or 'ден' in src):
            count = int(daily_cat.group('count'))
            cat = _extract_category_from_text(src)
            cat_label = cat or 'dance'
            buckets = [
                {'name': 'morning', 'start': '09:00', 'end': '14:00'},
                {'name': 'evening', 'start': '16:00', 'end': '21:00'},
            ]
            payload = {
                'rule_type': 'daily_duplicate_limit',
                'severity': 'hard',
                'name': f'Лимит {cat_label}: {count} вида в день',
                'params_json': {
                    'scope': 'bucket',
                    'max_per_bucket_per_day': count,
                    'category': cat_label,
                    'buckets': buckets,
                }
            }
            return payload, None

    # Если ни один шаблон не подошёл — возвращаем ошибку с пояснением
    return None, 'Не удалось распознать правило. Сейчас поддерживаются шаблоны: лимит в неделю, чередование, запрет дублей в день, ограничение подряд.'


# ═══════════════════════════════════════════════════════════
# Сериализация для фронтенда
# ═══════════════════════════════════════════════════════════

def _serialize_active_distribution_rules():
    """
    Сериализует активные правила для передачи в JS (create_schedule.html).

    Возвращает список словарей с ключами:
      id, name, rule_type, severity, params (params_json)

    Этот JSON попадает в шаблон как:
      const ACTIVE_DISTRIBUTION_RULES = {{ distribution_rules_json|safe }};
    и используется в checkRules() при автозаполнении.
    """
    # Запрашиваем из БД все активные правила, отсортированные по приоритету и ID
    rules = DistributionRule.objects.filter(is_active=True).order_by('priority', 'id')
    # Создаём пустой список для сериализованных правил
    serialized = []
    # Перебираем каждое правило из запроса
    for rule in rules:
        # Добавляем словарь с ключевыми полями правила
        serialized.append({
            # ID правила из БД
            'id': rule.id,
            # Название правила
            'name': rule.name,
            # Тип правила (weekly_limit, alternation, calm_consecutive, daily_duplicate_limit)
            'rule_type': rule.rule_type,
            # Жёсткость правила (hard — жёсткое, soft — мягкое)
            'severity': rule.severity,
            # Параметры правила (JSON-словарь) или пустой объект, если None
            'params': rule.params_json or {},
        })
    # Возвращаем готовый список для JSON-сериализации
    return serialized


# ═══════════════════════════════════════════════════════════
# Обнаружение конфликтов между правилами
# ═══════════════════════════════════════════════════════════
# Система проверяет, не противоречат ли правила друг другу.
# Например: одно правило говорит «силовые не чаще 3 раз в неделю»,
# а другое — «силовые не чаще 5 раз в неделю». Это конфликт.
#
# Конфликты бывают:
#   - hard — явное противоречие (разные лимиты на одно и то же)
#   - soft — потенциальное пересечение (схожие правила на одни дни)

def _bucket_signature(bucket: dict) -> str:
    """Создаёт строку-идентификатор временного окна (например, 'morning|09:00|14'00')."""
    # Склеиваем имя окна, время начала и время окончания через вертикальную черту; если bucket None или нет ключей — подставляем пустые строки
    return f"{(bucket or {}).get('name','')}|{(bucket or {}).get('start','')}|{(bucket or {}).get('end','')}"


def _extract_weekly_limit_map(rule: DistributionRule):
    """Извлекает из правила weekly_limit карту лимитов по временным окнам для сравнения."""
    # Если правило не является weekly_limit — возвращаем пустой словарь
    if rule.rule_type != 'weekly_limit':
        return {}
    # Получаем параметры правила (или пустой словарь, если None)
    params = rule.params_json or {}
    # Определяем режим цели: category (категория) или workout (конкретная тренировка)
    target_mode = params.get('target_mode') or ('category' if params.get('category') else 'workout')
    # Формируем ключ цели: если режим "category" — используем название категории, иначе нормализованное название тренировки
    target_key = (
        (params.get('category') or '').strip().lower()
        if target_mode == 'category'
        else _normalize_workout_name_for_rule(params.get('workout_name') or '')
    )
    # Если ключ цели пустой — возвращаем пустой словарь
    if not target_key:
        return {}
    # Создаём словарь для результатов
    result = {}
    # Перебираем все временные окна из параметров правила
    for bucket in (params.get('buckets') or []):
        try:
            # Пытаемся преобразовать лимит max в число
            max_value = int(bucket.get('max', 0))
        except Exception:
            # Если не получилось — ставим 0
            max_value = 0
        # Сохраняем в результат по сигнатуре окна: лимит, само окно, режим и ключ цели
        result[_bucket_signature(bucket)] = {
            'max': max_value,
            'bucket': bucket,
            'target_mode': target_mode,
            'target_key': target_key,
        }
    # Возвращаем карту лимитов для сравнения
    return result


def _extract_alternation_signature(rule: DistributionRule):
    """Извлекает подпись чередования для сравнения двух alternation-правил."""
    # Если правило не является alternation — возвращаем None
    if rule.rule_type != 'alternation':
        return None
    # Получаем параметры правила (или пустой словарь)
    params = rule.params_json or {}
    # Извлекаем список категорий, приводим к нижнему регистру, убираем пустые
    categories = [str(x).strip().lower() for x in (params.get('categories') or []) if str(x).strip()]
    # Извлекаем список дней недели, сортируем, убираем дубликаты
    weekdays = sorted(set(int(x) for x in (params.get('weekdays') or []) if str(x).strip().isdigit()))
    # Если категорий меньше 2 или нет дней — сигнатура невалидна
    if len(categories) < 2 or not weekdays:
        return None
    # Возвращаем словарь с кортежами категорий и дней для сравнения
    return {
        'categories': tuple(sorted(set(categories))),
        'weekdays': tuple(weekdays),
    }


def _build_distribution_rules_conflicts(rules):
    """
    Ищет конфликты между правилами распределения.

    Проходим по всем парам активных правил и проверяем:
    1. Weekly_limit на один target с разными max в одном окне → hard-конфликт
    2. Alternation на пересекающиеся дни с общей категорией → soft-конфликт
    3. Alternation с 3+ категориями vs 2 категории на те же дни → hard-конфликт
    4. Два hard weekly_limit одного типа → soft-предупреждение

    Возвращает список словарей с полями: level (hard/soft), title, rule_a, rule_b,
    description, how_to_fix.
    """
    # Фильтруем только активные правила из переданного списка
    active_rules = [r for r in rules if r.is_active]
    # Создаём пустой список для найденных конфликтов
    conflicts = []

    # Внешний цикл по всем активным правилам (первое правило в паре)
    for i in range(len(active_rules)):
        # Внутренний цикл по всем правилам после i (второе правило в паре)
        for j in range(i + 1, len(active_rules)):
            # Первое правило пары
            a = active_rules[i]
            # Второе правило пары
            b = active_rules[j]

            # 1) Явный конфликт: два weekly_limit на один target, одно окно, разные max
            # Извлекаем карту лимитов первого правила
            a_week = _extract_weekly_limit_map(a)
            # Извлекаем карту лимитов второго правила
            b_week = _extract_weekly_limit_map(b)
            # Если оба правила — weekly_limit и имеют карту лимитов
            if a_week and b_week:
                # Перебираем все окна первого правила
                for bucket_key, a_data in a_week.items():
                    # Пытаемся найти такое же окно во втором правиле
                    b_data = b_week.get(bucket_key)
                    # Если окна нет во втором правиле — пропускаем
                    if not b_data:
                        continue
                    # Если режим цели или ключ цели не совпадают — пропускаем (разные тренировки)
                    if a_data['target_mode'] != b_data['target_mode'] or a_data['target_key'] != b_data['target_key']:
                        continue
                    # Если лимиты различаются — это конфликт
                    if a_data['max'] != b_data['max']:
                        # Добавляем hard-конфликт в список
                        conflicts.append({
                            'level': 'hard',
                            'title': 'Противоречивые лимиты',
                            'rule_a': a,
                            'rule_b': b,
                            'description': (
                                f'Для одного и того же ограничения заданы разные лимиты '
                                f'в окне "{a_data["bucket"].get("name", "slot")}".'
                            ),
                            'how_to_fix': 'Оставьте один лимит или сделайте одинаковые значения max в обоих правилах.',
                        })

            # 2) Потенциальный конфликт: две alternation со схожими днями и общей категорией
            # Извлекаем сигнатуру чередования первого правила
            a_alt = _extract_alternation_signature(a)
            # Извлекаем сигнатуру чередования второго правила
            b_alt = _extract_alternation_signature(b)
            # Если оба правила — alternation и имеют валидные сигнатуры
            if a_alt and b_alt:
                # Находим пересечение дней недели
                weekdays_intersection = set(a_alt['weekdays']) & set(b_alt['weekdays'])
                # Находим пересечение категорий
                categories_intersection = set(a_alt['categories']) & set(b_alt['categories'])
                # Количество категорий в первом правиле
                a_cnt = len(set(a_alt['categories']))
                # Количество категорий во втором правиле
                b_cnt = len(set(b_alt['categories']))
                # Флаг: одно правило широкое (3+ категории), другое — узкое (2 категории)
                mixed_scope = (a_cnt >= 3 and b_cnt == 2) or (b_cnt >= 3 and a_cnt == 2)

                # Если есть пересечение дней, есть пересечение категорий, наборы категорий разные, и не mixed_scope
                if (
                    weekdays_intersection
                    and categories_intersection
                    and set(a_alt['categories']) != set(b_alt['categories'])
                    and not mixed_scope
                ):
                    # Добавляем soft-конфликт (потенциальная нестабильность)
                    conflicts.append({
                        'level': 'soft',
                        'title': 'Возможный конфликт чередования',
                        'rule_a': a,
                        'rule_b': b,
                        'description': (
                            'Для пересекающихся дней заданы разные пары категорий чередования. '
                            'Алгоритм может заполнять такие дни нестабильно.'
                        ),
                        'how_to_fix': 'Разведите правила по разным дням недели или оставьте одну пару категорий на один набор дней.',
                    })

                # 2.1) Усиленный конфликт: 3+ категорий vs 2 категории на пересекающиеся дни
                # Если есть пересечение дней и одно правило широкое, другое узкое
                if weekdays_intersection and ((a_cnt >= 3 and b_cnt == 2) or (b_cnt >= 3 and a_cnt == 2)):
                    # Добавляем hard-конфликт
                    conflicts.append({
                        'level': 'hard',
                        'title': 'Противоречивые схемы чередования',
                        'rule_a': a,
                        'rule_b': b,
                        'description': (
                            'Широкое правило чередования (с 3+ категориями) пересекается с узким '
                            'правилом (2 категории) по тем же дням.'
                        ),
                        'how_to_fix': 'Оставьте одно правило чередования на эти дни или разделите дни между правилами.',
                    })

            # 3) Предупреждение: два hard правила одного типа
            # Если у правил одинаковый тип и оба жёсткие
            if a.rule_type == b.rule_type and a.severity == 'hard' and b.severity == 'hard':
                # Дополнительная проверка: если это weekly_limit и у обоих есть карта лимитов
                if a.rule_type == 'weekly_limit' and _extract_weekly_limit_map(a) and _extract_weekly_limit_map(b):
                    # Добавляем soft-предупреждение о дублировании
                    conflicts.append({
                        'level': 'soft',
                        'title': 'Перекрывающиеся жесткие weekly_limit',
                        'rule_a': a,
                        'rule_b': b,
                        'description': 'Два жестких weekly_limit могут дублировать друг друга и усложнять отладку.',
                        'how_to_fix': 'Объедините их в одно правило или понизьте жесткость/измените приоритет одного из них.',
                    })

    # Возвращаем список всех найденных конфликтов
    return conflicts


# ═══════════════════════════════════════════════════════════
# Страница правил распределения
# ═══════════════════════════════════════════════════════════

# Декоратор: только авторизованный пользователь может зайти
@login_required
# Декоратор: только менеджер (проверка is_manager) может зайти
@user_passes_test(is_manager)
def distribution_rules_page(request):
    """
    Главная страница управления правилами (/schedules/rules/).

    Загружает все правила, проверяет конфликты и рендерит шаблон.
    В шаблон передаются:
      - rules — все правила для таблицы
      - rules_conflicts — найденные конфликты
      - conflict_rule_ids — ID правил-участников конфликтов (для подсветки)
    """
    # Загружаем все правила из БД с присоединённым создателем, сортируем по приоритету и ID
    rules = DistributionRule.objects.all().select_related('created_by').order_by('priority', 'id')
    # Строим список конфликтов между правилами
    conflicts = _build_distribution_rules_conflicts(list(rules))
    # Множество ID всех правил, участвующих в конфликтах
    conflict_rule_ids = set()
    # Множество ID правил с hard-конфликтами
    conflict_rule_hard_ids = set()
    # Множество ID правил с soft-конфликтами
    conflict_rule_soft_ids = set()
    # Перебираем все найденные конфликты
    for c in conflicts:
        # Определяем уровень конфликта (по умолчанию soft)
        level = c.get('level') or 'soft'
        # Если есть первое правило-участник — добавляем его ID
        if c.get('rule_a'):
            rid = c['rule_a'].id
            conflict_rule_ids.add(rid)
            # Если конфликт hard — в hard-множество, иначе — в soft
            if level == 'hard':
                conflict_rule_hard_ids.add(rid)
            else:
                conflict_rule_soft_ids.add(rid)
        # Если есть второе правило-участник — добавляем его ID
        if c.get('rule_b'):
            rid = c['rule_b'].id
            conflict_rule_ids.add(rid)
            # Если конфликт hard — в hard-множество, иначе — в soft
            if level == 'hard':
                conflict_rule_hard_ids.add(rid)
            else:
                conflict_rule_soft_ids.add(rid)
    # Из soft-множества убираем те ID, которые уже есть в hard (приоритет hard)
    conflict_rule_soft_ids = conflict_rule_soft_ids - conflict_rule_hard_ids
    # Рендерим страницу с шаблоном и передаём все данные в контексте
    return render(
        request,
        'core/schedules/distribution_rules.html',
        {
            # Список всех правил
            'rules': rules,
            # Список конфликтов
            'rules_conflicts': conflicts,
            # Количество конфликтов
            'rules_conflicts_count': len(conflicts),
            # Отсортированный список ID правил-участников конфликтов
            'conflict_rule_ids': sorted(conflict_rule_ids),
            # Отсортированный список ID правил с hard-конфликтами
            'conflict_rule_hard_ids': sorted(conflict_rule_hard_ids),
            # Отсортированный список ID правил с soft-конфликтами (без hard)
            'conflict_rule_soft_ids': sorted(conflict_rule_soft_ids),
        }
    )


# ═══════════════════════════════════════════════════════════
# API: парсинг текста правила (ИИ → fallback-regex)
# ═══════════════════════════════════════════════════════════

# Декоратор: только авторизованный пользователь
@login_required
# Декоратор: только менеджер
@user_passes_test(is_manager)
def api_parse_distribution_rule(request):
    """
    POST-эндпоинт для распознавания текста правила.

    Алгоритм:
      1. Пробуем шаблонный парсер (_parse_distribution_rule_text)
      2. Если не смог — возвращаем ошибку

    Возвращает JSON с parsed (структура правила), source (ai/fallback_regex),
    explanation, confidence.
    """
    # Проверяем, что метод запроса — POST
    if request.method != 'POST':
        # Если нет — возвращаем ошибку 405
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается.'}, status=405)
    try:
        # Пытаемся декодировать тело запроса из JSON
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        # Если не удалось — используем пустой словарь
        payload = {}
    # Извлекаем текст правила, обрезаем пробелы
    text = (payload.get('text') or '').strip()
    # Если текст пустой — возвращаем ошибку 400
    if not text:
        return JsonResponse({'success': False, 'error': 'Введите текст правила.'}, status=400)

    # Шаг 1: regex (мгновенно)
    # Пробуем распарсить текст шаблонным парсером (без ИИ)
    parsed, error = _parse_distribution_rule_text(text)
    # Если ошибки нет — значит шаблон сработал
    if not error:
        # Возвращаем успешный ответ с результатом regex-парсинга
        return JsonResponse({
            'success': True,
            'parsed': parsed,
            'source': 'regex',
            'explanation': 'Распознано шаблонным парсером.',
            'confidence': 0.92,
        })

    # Шаг 2: AI (медленно) — только если regex не справился
    ai_result = try_parse_rule_with_ai(text)
    # Если AI успешно распознал правило
    if ai_result.get('success'):
        # Возвращаем успешный ответ с результатом AI-парсинга
        return JsonResponse({
            'success': True,
            'parsed': ai_result['parsed'],
            'source': 'ai',
            'explanation': ai_result.get('explanation') or 'Распознано с помощью ИИ.',
            'confidence': ai_result.get('confidence', 0.85),
        })

    # Если ни regex, ни AI не справились — возвращаем ошибку 400 с текстом ошибки
    return JsonResponse({'success': False, 'error': error}, status=400)


# ═══════════════════════════════════════════════════════════
# API: сохранение правила
# ═══════════════════════════════════════════════════════════

# Декоратор: только авторизованный пользователь
@login_required
# Декоратор: только менеджер
@user_passes_test(is_manager)
def api_save_distribution_rule(request):
    """
    POST-эндпоинт для сохранения распознанного правила в БД.

    Принимает source_text (оригинальный текст) и parsed (распознанную структуру).
    Создаёт DistributionRule и проверяет конфликты с уже существующими правилами.
    """
    # Проверяем, что метод запроса — POST
    if request.method != 'POST':
        # Если нет — возвращаем ошибку 405
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается.'}, status=405)
    try:
        # Пытаемся декодировать тело запроса из JSON
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        # Если не удалось — используем пустой словарь
        payload = {}
    # Извлекаем исходный текст правила, обрезаем пробелы
    source_text = (payload.get('source_text') or '').strip()
    # Извлекаем распознанную структуру правила
    parsed = payload.get('parsed') or {}
    # Если исходный текст пустой — ошибка
    if not source_text:
        return JsonResponse({'success': False, 'error': 'Пустой текст правила.'}, status=400)
    # Если нет распознанных данных или нет rule_type — ошибка
    if not parsed or not parsed.get('rule_type'):
        return JsonResponse({'success': False, 'error': 'Нет распознанных данных правила.'}, status=400)

    # Создаём новое правило в БД
    rule = DistributionRule.objects.create(
        # Название: из payload, или из parsed, или первые 180 символов source_text; не более 200
        name=(payload.get('name') or parsed.get('name') or source_text[:180]).strip()[:200],
        # Исходный текст правила
        source_text=source_text,
        # Тип правила из распознанной структуры
        rule_type=parsed.get('rule_type'),
        # Жёсткость: если не hard и не soft — по умолчанию hard
        severity=parsed.get('severity') if parsed.get('severity') in {'hard', 'soft'} else 'hard',
        # Параметры правила (JSON) или пустой словарь
        params_json=parsed.get('params_json') or {},
        # Активно ли правило (по умолчанию True)
        is_active=bool(payload.get('is_active', True)),
        # Приоритет (по умолчанию 100)
        priority=int(payload.get('priority', 100) or 100),
        # Пользователь, создавший правило
        created_by=request.user,
    )
    # После сохранения — проверяем конфликты со всеми правилами в БД
    conflicts = _build_distribution_rules_conflicts(
        list(DistributionRule.objects.all().order_by('priority', 'id'))
    )
    # Возвращаем успешный ответ с ID созданного правила и количеством конфликтов
    return JsonResponse({
        'success': True,
        'rule_id': rule.id,
        'conflicts_count': len(conflicts),
    })


# ═══════════════════════════════════════════════════════════
# API: включение/выключение правила
# ═══════════════════════════════════════════════════════════

# Декоратор: только авторизованный пользователь
@login_required
# Декоратор: только менеджер
@user_passes_test(is_manager)
def api_toggle_distribution_rule(request, rule_id):
    """Переключает is_active у правила (вкл/выкл) без удаления."""
    # Проверяем, что метод запроса — POST
    if request.method != 'POST':
        # Если нет — возвращаем ошибку 405
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается.'}, status=405)
    # Получаем правило из БД по ID или возвращаем 404
    rule = get_object_or_404(DistributionRule, id=rule_id)
    # Инвертируем флаг активности
    rule.is_active = not rule.is_active
    # Сохраняем только поля is_active и updated_at (не трогаем остальные)
    rule.save(update_fields=['is_active', 'updated_at'])
    # Возвращаем успешный ответ с новым состоянием
    return JsonResponse({'success': True, 'is_active': rule.is_active})


# ═══════════════════════════════════════════════════════════
# API: удаление правила
# ═══════════════════════════════════════════════════════════

# Декоратор: только авторизованный пользователь
@login_required
# Декоратор: только менеджер
@user_passes_test(is_manager)
def api_delete_distribution_rule(request, rule_id):
    """Полностью удаляет правило распределения из БД."""
    # Проверяем, что метод запроса — POST
    if request.method != 'POST':
        # Если нет — возвращаем ошибку 405
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается.'}, status=405)
    # Получаем правило из БД по ID или возвращаем 404
    rule = get_object_or_404(DistributionRule, id=rule_id)
    # Удаляем правило из БД
    rule.delete()
    # Возвращаем успешный ответ
    return JsonResponse({'success': True})


# ═══════════════════════════════════════════════════════════
# API: обновление правила (название, жёсткость, приоритет)
# ═══════════════════════════════════════════════════════════

# Декоратор: только авторизованный пользователь
@login_required
# Декоратор: только менеджер
@user_passes_test(is_manager)
def api_update_distribution_rule(request, rule_id):
    """Обновляет название, жёсткость и приоритет существующего правила."""
    # Проверяем, что метод запроса — POST
    if request.method != 'POST':
        # Если нет — возвращаем ошибку 405
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается.'}, status=405)
    # Получаем правило из БД по ID или возвращаем 404
    rule = get_object_or_404(DistributionRule, id=rule_id)
    try:
        # Пытаемся декодировать тело запроса из JSON
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        # Если не удалось — используем пустой словарь
        payload = {}

    # Извлекаем новое название (обрезаем пробелы)
    name = (payload.get('name') or '').strip()
    # Извлекаем новую жёсткость (обрезаем пробелы)
    severity = (payload.get('severity') or '').strip()
    # Извлекаем новый приоритет (или оставляем текущий)
    priority_raw = payload.get('priority', rule.priority)

    # Если название не пустое — обновляем (максимум 200 символов)
    if name:
        rule.name = name[:200]
    # Если жёсткость валидна (hard или soft) — обновляем
    if severity in {'hard', 'soft'}:
        rule.severity = severity
    try:
        # Пытаемся преобразовать приоритет в число (минимум 1)
        rule.priority = max(1, int(priority_raw))
    except Exception:
        # Если не получилось — ничего не делаем
        pass

    # Сохраняем только изменённые поля + updated_at
    rule.save(update_fields=['name', 'severity', 'priority', 'updated_at'])
    # Возвращаем успешный ответ с обновлёнными данными правила
    return JsonResponse({
        'success': True,
        'rule': {
            'id': rule.id,
            'name': rule.name,
            'severity': rule.severity,
            'priority': rule.priority,
        }
    })


# ═══════════════════════════════════════════════════════════
# Утилиты для тестирования правил
# ═══════════════════════════════════════════════════════════

def _infer_category_from_name(workout_name: str) -> str:
    """
    Пытается определить категорию тренировки по её названию.

    Используется в api_test_distribution_rules, когда у направления
    не указана категория явно. Анализирует ключевые слова.
    """
    # Приводим название к нижнему регистру; если None — пустая строка
    n = (workout_name or '').lower()
    # Если в названии есть "табата", "кардио", "cardio", "hiit" — возвращаем cardio
    if any(x in n for x in ['табата', 'кардио', 'cardio', 'hiit']):
        return 'cardio'
    # Если в названии есть "сил", "strength", "power" — возвращаем strength
    if any(x in n for x in ['сил', 'strength', 'power']):
        return 'strength'
    # Если в названии есть "dance", "танц", "bachata", "восточ", "стрип" — возвращаем dance
    if any(x in n for x in ['dance', 'танц', 'bachata', 'восточ', 'стрип']):
        return 'dance'
    # Если в названии есть "stretch", "растяж", "йог", "calm", "спокой" — возвращаем calm
    if any(x in n for x in ['stretch', 'растяж', 'йог', 'calm', 'спокой']):
        return 'calm'
    # Если ничего не подошло — возвращаем "other" (другое)
    return 'other'


def _normalize_workout_name_for_rule(name: str) -> str:
    """
    Приводит название тренировки к канонической форме для сравнения.

    Нужно, чтобы «табата» и «tabata» считались одним и тем же направлением.
    Также нормализует грамматические формы: «табату», «табатой» → «табата» → «tabata».
    """
    # Приводим к нижнему регистру, обрезаем пробелы
    n = (name or '').strip().lower()
    # Словарь алиасов: русские названия → английские эквиваленты
    aliases = {
        'табата': 'tabata',
        'стретчинг': 'stretching',
        'растяжка': 'stretching',
        'бачата': 'bachata',
        'силовые': 'strength',
        'кардио': 'cardio',
    }
    # Если имя есть в алиасах — возвращаем английский вариант
    result = aliases.get(n)
    if result:
        return result
    # Пробуем найти алиас по подстроке
    for alias, normalized in aliases.items():
        if alias in n or n in alias:
            return normalized
    # Пробуем отбросить окончание: «табату» → «табат» → ищем алиас с тем же корнем
    stem = re.sub(r'[аяуюоеиы]$', '', n)
    if stem and stem != n:
        for alias, normalized in aliases.items():
            alias_stem = re.sub(r'[аяуюоеиы]$', '', alias)
            if alias_stem == stem:
                return normalized
    return n


def _time_in_bucket(start_time, bucket):
    """Проверяет, попадает ли время начала занятия в заданное окно (утро/вечер)."""
    # Преобразуем время начала в строку "ЧЧ:ММ"
    st = start_time.strftime('%H:%M')
    # Проверяем: время начала >= начало окна И время начала < конец окна
    return (bucket.get('start') or '00:00') <= st < (bucket.get('end') or '23:59')


# ═══════════════════════════════════════════════════════════
# API: тестирование правил на существующих графиках
# ═══════════════════════════════════════════════════════════

# Декоратор: только авторизованный пользователь
@login_required
# Декоратор: только менеджер
@user_passes_test(is_manager)
def api_test_distribution_rules(request):
    """
    POST-эндпоинт: проверяет активные правила на назначениях в указанном периоде.

    Проходит по всем назначениям (ShiftAssignment) и для каждого проверяет
    все активные правила. Если правило нарушено — добавляет запись в violations.

    Это серверный аналог JS-функции checkRules() из create_schedule.html.
    Используется на странице правил для отладки: менеджер задаёт период
    и смотрит, какие нарушения нашлись.
    """
    # Проверяем, что метод запроса — POST
    if request.method != 'POST':
        # Если нет — возвращаем ошибку 405
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается.'}, status=405)
    try:
        # Пытаемся декодировать тело запроса из JSON
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        # Если не удалось — используем пустой словарь
        payload = {}

    # Извлекаем начальную дату периода
    start_raw = (payload.get('start_date') or '').strip()
    # Извлекаем конечную дату периода
    end_raw = (payload.get('end_date') or '').strip()
    # Если одна из дат не указана — ошибка
    if not start_raw or not end_raw:
        return JsonResponse({'success': False, 'error': 'Укажите период.'}, status=400)
    try:
        # Парсим начальную дату из строки формата YYYY-MM-DD
        start_date = datetime.strptime(start_raw, '%Y-%m-%d').date()
        # Парсим конечную дату из строки формата YYYY-MM-DD
        end_date = datetime.strptime(end_raw, '%Y-%m-%d').date()
    except Exception:
        # Если формат неправильный — ошибка
        return JsonResponse({'success': False, 'error': 'Некорректный формат даты.'}, status=400)
    # Если начальная дата больше конечной — меняем их местами
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    # Загружаем все активные правила, отсортированные по приоритету и ID
    rules = list(DistributionRule.objects.filter(is_active=True).order_by('priority', 'id'))
    # Загружаем все назначения в указанном периоде, у которых есть тип тренировки
    assignments = list(
        ShiftAssignment.objects.filter(
            # Дата не раньше начальной
            date__gte=start_date,
            # Дата не позже конечной
            date__lte=end_date,
            # Только назначения с указанным типом тренировки
            workout_type__isnull=False,
        # Присоединяем связанные модели workout_type и employee.user
        ).select_related('workout_type', 'employee__user')
    )
    # Сортируем назначения по дате и времени начала
    assignments.sort(key=lambda a: (a.date, a.start_time))

    # Счётчик нарушений — список словарей с деталями
    violations = []
    # Словарь: сколько уже поставили в конкретное weekly-окно (ключ: rule_id|week_key|bucket)
    weekly_counts = {}         # weekly bucket: сколько уже поставили
    # Словарь: общее количество за неделю без разбивки по окнам (ключ: rule_id|week_key|total)
    weekly_total_counts = {}   # weekly total: общее количество за неделю
    # Словарь: сколько одинаковых тренировок в одном дне/окне (ключ: rule_id|day_key|bucket|workout)
    daily_bucket_workout_counts = {}  # daily: сколько одинаковых в одном окне
    # Словарь: текущая длина серии подряд (streak) для calm_consecutive (ключ: day_key)
    calm_streaks = {}          # consecutive: streak подряд
    # Словарь: какая категория была последней для alternation (ключ: day_key)
    prev_category = {}         # alternation: какая категория была последней

    # Перебираем все назначения в отсортированном порядке
    for a in assignments:
        # Получаем название тренировки; если нет workout_type_id — пустая строка
        workout_name = a.workout_type.name if a.workout_type_id else ''
        # Определяем категорию тренировки
        category = (
            # Если у workout_type есть поле category — используем его
            a.workout_type.category
            if getattr(a.workout_type, 'category', None)
            # Иначе пытаемся определить категорию по названию
            else _infer_category_from_name(workout_name)
        )
        # Получаем день недели (0=пн ... 6=вс)
        weekday = a.date.weekday()
        # Строковый ключ дня в формате ISO (YYYY-MM-DD)
        day_key = a.date.isoformat()
        # Строковый ключ недели в формате "год-номер_недели"
        week_key = f"{a.date.isocalendar().year}-{a.date.isocalendar().week}"

        # Перебираем все активные правила
        for rule in rules:
            # Получаем параметры правила (или пустой словарь)
            params = rule.params_json or {}

            # ── weekly_limit: лимит на неделю ──
            # Проверяем, является ли правило weekly_limit
            if rule.rule_type == 'weekly_limit':
                # Определяем режим цели: category или workout
                target_mode = params.get('target_mode') or (
                    'category' if params.get('category') else 'workout'
                )
                # Нормализованное название тренировки из правила
                target_workout = _normalize_workout_name_for_rule(params.get('workout_name') or '')
                # Категория из правила (обрезаем пробелы)
                target_category = (params.get('category') or '').strip()
                # Нормализованное название текущей тренировки
                workout_norm = _normalize_workout_name_for_rule(workout_name)
                # Флаг: подходит ли это назначение под проверяемое правило
                is_match = False
                # Если режим — категория
                if target_mode == 'category':
                    # Совпадает категория назначения с категорией правила
                    is_match = bool(target_category and category == target_category)
                else:
                    # Иначе — название тренировки должно содержать цель правила
                    is_match = bool(target_workout and target_workout in workout_norm)

                # Если назначение подходит под правило — проверяем лимиты
                if is_match:
                    # Проверка общего лимита (max_total)
                    # Ключ для подсчёта: ID правила + неделя + "total"
                    total_key = f"{rule.id}|{week_key}|total"
                    # Увеличиваем счётчик total на этой неделе
                    weekly_total_counts[total_key] = weekly_total_counts.get(total_key, 0) + 1
                    # Если задан max_total и текущее количество превышает лимит
                    if params.get('max_total') is not None and weekly_total_counts[total_key] > int(params.get('max_total', 0)):
                        # Добавляем запись о нарушении
                        violations.append({
                            'rule': rule.name,
                            'date': a.date.strftime('%d.%m.%Y'),
                            'time': a.start_time.strftime('%H:%M'),
                            'workout': workout_name,
                            'employee': a.employee.user.username,
                            'reason': 'Превышен общий недельный лимит',
                        })

                    # Проверка лимитов по временным окнам (утро/вечер)
                    # Перебираем все временные окна из параметров
                    for b in (params.get('buckets') or []):
                        # Если время назначения попадает в это окно
                        if _time_in_bucket(a.start_time, b):
                            # Ключ для подсчёта: ID правила + неделя + название окна
                            key = f"{rule.id}|{week_key}|{b.get('name','bucket')}"
                            # Увеличиваем счётчик назначений в этом окне на этой неделе
                            weekly_counts[key] = weekly_counts.get(key, 0) + 1
                            # Если превышен лимит окна — добавляем нарушение
                            if weekly_counts[key] > int(b.get('max', 0)):
                                violations.append({
                                    'rule': rule.name,
                                    'date': a.date.strftime('%d.%m.%Y'),
                                    'time': a.start_time.strftime('%H:%M'),
                                    'workout': workout_name,
                                    'employee': a.employee.user.username,
                                    'reason': f'Превышен лимит "{b.get("name", "bucket")}" за неделю',
                                })

            # ── calm_consecutive: лимит спокойных/силовых подряд ──
            # Проверяем, является ли правило calm_consecutive
            elif rule.rule_type == 'calm_consecutive':
                # Список дней, на которые распространяется правило
                weekdays = params.get('weekdays') or []
                # Максимум подряд (по умолчанию 2)
                max_consecutive = int(params.get('max_consecutive', 2))
                # Ожидаемая категория (calm или strength)
                expected = params.get('category', 'calm')
                # Если сегодня — подходящий день недели
                if weekday in weekdays:
                    # Если категория назначения совпадает с ожидаемой
                    if category == expected:
                        # Увеличиваем счётчик подряд для этого дня
                        calm_streaks[day_key] = calm_streaks.get(day_key, 0) + 1
                        # Если streak превышает максимум — нарушение
                        if calm_streaks[day_key] > max_consecutive:
                            violations.append({
                                'rule': rule.name,
                                'date': a.date.strftime('%d.%m.%Y'),
                                'time': a.start_time.strftime('%H:%M'),
                                'workout': workout_name,
                                'employee': a.employee.user.username,
                                'reason': 'Слишком много спокойных подряд',
                            })
                    else:
                        # Другая категория — сбрасываем счётчик
                        calm_streaks[day_key] = 0

            # ── alternation: чередование категорий ──
            # Проверяем, является ли правило alternation
            elif rule.rule_type == 'alternation':
                # Список дней недели для чередования
                weekdays = params.get('weekdays') or []
                # Список категорий для чередования (по умолчанию strength и cardio)
                categories = params.get('categories') or ['strength', 'cardio']
                # Если сегодня — подходящий день, и категория входит в список
                if weekday in weekdays and category in categories:
                    # Если предыдущая категория в этот день совпадает с текущей — нарушение
                    if prev_category.get(day_key) == category:
                        # Та же категория дважды подряд — нарушение
                        violations.append({
                            'rule': rule.name,
                            'date': a.date.strftime('%d.%m.%Y'),
                            'time': a.start_time.strftime('%H:%M'),
                            'workout': workout_name,
                            'employee': a.employee.user.username,
                            'reason': 'Нарушено чередование категорий',
                        })
                    # Запоминаем текущую категорию как последнюю для этого дня
                    prev_category[day_key] = category

            # ── daily_duplicate_limit: запрет дублей в день ──
            elif rule.rule_type == 'daily_duplicate_limit':
                buckets = params.get('buckets') or []
                max_per_bucket_per_day = int(params.get('max_per_bucket_per_day', 1))
                rule_category = (params.get('category') or '').strip()
                for b in buckets:
                    if _time_in_bucket(a.start_time, b):
                        if rule_category:
                            if category != rule_category:
                                continue
                            key = f"{rule.id}|{day_key}|{b.get('name','bucket')}|cat:{rule_category}"
                        else:
                            workout_norm = _normalize_workout_name_for_rule(workout_name)
                            key = f"{rule.id}|{day_key}|{b.get('name','bucket')}|{workout_norm}"
                        daily_bucket_workout_counts[key] = daily_bucket_workout_counts.get(key, 0) + 1
                        if daily_bucket_workout_counts[key] > max_per_bucket_per_day:
                            v = {
                                'rule': rule.name,
                                'date': a.date.strftime('%d.%m.%Y'),
                                'time': a.start_time.strftime('%H:%M'),
                                'workout': workout_name,
                                'employee': a.employee.user.username,
                            }
                            if rule_category:
                                v['reason'] = f'Слишком много тренировок категории "{rule_category}" в одном окне дня'
                            else:
                                v['reason'] = 'Одинаковая тренировка повторяется в одном окне дня'
                            violations.append(v)

    # Возвращаем JSON-ответ со всеми найденными нарушениями
    return JsonResponse({
        'success': True,
        # Период, в котором проводилось тестирование
        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
        },
        # Количество проверенных правил
        'rules_count': len(rules),
        # Общее количество нарушений
        'violations_count': len(violations),
        # Список нарушений (ограничен 150 записями, чтобы не сломать JSON)
        'violations': violations[:150],  # Ограничиваем вывод, чтобы не сломать JSON
    })
