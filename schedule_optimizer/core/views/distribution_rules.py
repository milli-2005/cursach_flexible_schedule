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

from .auth import *

# ═══════════════════════════════════════════════════════════
# Константы студийных слотов (9:00–21:00, обед 14:00–16:00)
# ═══════════════════════════════════════════════════════════
# Студия работает с 9 до 21. Одно занятие = 50 мин + 10 мин перерыв.
# Обеденный перерыв 14:00–16:00 — в это время слоты не создаются.
STUDIO_DAY_START_MIN = 9 * 60    # 09:00 в минутах
STUDIO_DAY_END_MIN = 21 * 60     # 21:00 в минутах
SLOT_WORK_MIN = 50               # Длительность занятия
SLOT_BREAK_MIN = 10              # Перерыв между занятиями
STUDIO_LUNCH_START_MIN = 14 * 60 # Начало обеда
STUDIO_LUNCH_END_MIN = 16 * 60   # Конец обеда


def _generate_studio_slots():
    """
    Генерирует временные слоты для расписания.

    Возвращает список кортежей (start_str, end_str), например:
    [('09:00', '09:50'), ('10:00', '10:50'), ..., ('20:00', '20:50')]

    Обед 14:00–16:00 пропускается — слотов в это время нет.
    Используется в create_schedule_view, edit_schedule_view, schedule_detail.
    """
    slots = []
    current_time = STUDIO_DAY_START_MIN
    while current_time + SLOT_WORK_MIN <= STUDIO_DAY_END_MIN:
        start_min = current_time
        end_min = current_time + SLOT_WORK_MIN
        # Проверяем, попадает ли слот на обед (целиком или частично)
        intersects_lunch = start_min < STUDIO_LUNCH_END_MIN and end_min > STUDIO_LUNCH_START_MIN
        if not intersects_lunch:
            start_str = f"{start_min // 60:02d}:{start_min % 60:02d}"
            end_str = f"{end_min // 60:02d}:{end_min % 60:02d}"
            slots.append((start_str, end_str))
        # Сдвигаемся на длину слота + перерыв
        current_time = end_min + SLOT_BREAK_MIN
    return slots


# ═══════════════════════════════════════════════════════════
# Fallback-парсер (без ИИ)
# ═══════════════════════════════════════════════════════════
# Если ИИ недоступен (нет ключа или ошибка), подключается этот парсер.
# Он ищет ключевые слова в тексте и сопоставляет их с шаблонами.
# Поддерживает ~10 популярных формулировок на русском.

# Словарь для перевода русских названий дней недели в индексы (0=пн ... 6=вс)
DAY_NAME_TO_INDEX = {
    'понедельник': 0, 'пн': 0,
    'вторник': 1, 'вт': 1,
    'среда': 2, 'ср': 2,
    'четверг': 3, 'чт': 3,
    'пятница': 4, 'пт': 4,
    'суббота': 5, 'сб': 5,
    'воскресенье': 6, 'вс': 6,
}


def _normalize_rule_text(text: str) -> str:
    """Приводит текст к нижнему регистру и схлопывает лишние пробелы."""
    return re.sub(r'\s+', ' ', (text or '').strip().lower())


# Соответствие русских названий занятий английским категориям (для выбора bucket в алгоритме)
# Ключ — подстрока, которая может быть в тексте правила; значение — категория
WORKOUT_CATEGORY_ALIASES = {
    'спокойн': 'calm',
    'calm': 'calm',
    'йога': 'calm',
    'стретч': 'calm',
    'растяж': 'calm',
    'пилатес': 'calm',
    'кардио': 'cardio',
    'cardio': 'cardio',
    'табата': 'cardio',
    'hiit': 'cardio',
    'силов': 'strength',
    'strength': 'strength',
    'power': 'strength',
    'танц': 'dance',
    'dance': 'dance',
    'бачата': 'dance',
    'стрип': 'dance',
    'восточ': 'dance',
}


def _extract_category_from_text(src: str):
    """Проверяет, есть ли в тексте слово-маркер категории (йога=calm, табата=cardio и т.д.)."""
    for key, value in WORKOUT_CATEGORY_ALIASES.items():
        if key in src:
            return value
    return None


def _parse_distribution_rule_text(text: str):
    """
    Парсит текст правила без ИИ, только по шаблонам.

    Каждый шаблон — это регулярное выражение, которое ищет ключевые слова
    (утро/вечер/неделя/подряд/чередование) и извлекает числа-ограничения.

    Возвращает (payload_dict, None) при успехе или (None, error_string) при ошибке.
    """
    src = _normalize_rule_text(text)
    if not src:
        return None, 'Введите текст правила.'

    # ── Шаблон 1: «Табата не более 1 раза утром и 1 раза вечером в неделю» ──
    # Ищет: "что-то не более N раз утром M раз вечером в неделю"
    weekly_pattern = re.search(
        r'(?P<target>[а-яa-z0-9 \-_]+?)\s+.*?не более\s+(?P<morning>\d+)\s+раз.*?утр.*?(?P<evening>\d+)\s+раз.*?вечер.*?недел',
        src
    )
    if weekly_pattern:
        raw_target = weekly_pattern.group('target').strip(' "«»')
        target_category = _extract_category_from_text(raw_target)
        morning_max = int(weekly_pattern.group('morning'))
        evening_max = int(weekly_pattern.group('evening'))
        params = {
            'period': 'week',
            'buckets': [
                {'name': 'morning', 'start': '09:00', 'end': '14:00', 'max': morning_max},
                {'name': 'evening', 'start': '16:00', 'end': '21:00', 'max': evening_max},
            ],
        }
        if target_category:
            params.update({'target_mode': 'category', 'category': target_category})
            title = f'Лимит категории "{target_category}" по неделе'
        else:
            params.update({'target_mode': 'workout', 'workout_name': raw_target})
            title = f'Лимит "{raw_target}" по неделе'
        payload = {
            'rule_type': 'weekly_limit',
            'severity': 'hard',
            'name': title,
            'params_json': params
        }
        return payload, None

    # ── Шаблон 1.1: «табата только 2 раза в неделю» / «не более 2 раз в неделю» ──
    total_week_pattern = re.search(
        r'(?P<target>[а-яa-z0-9 \-_]+?)\s+.*?(?:только|не более)\s+(?P<count>\d+)\s+раз\w*\s+.*?недел',
        src
    )
    if total_week_pattern:
        raw_target = total_week_pattern.group('target').strip(' "«»')
        target_category = _extract_category_from_text(raw_target)
        total_max = int(total_week_pattern.group('count'))
        params = {'period': 'week', 'max_total': total_max}
        if target_category:
            params.update({'target_mode': 'category', 'category': target_category})
            title = f'Лимит категории "{target_category}" за неделю'
        else:
            params.update({'target_mode': 'workout', 'workout_name': raw_target})
            title = f'Лимит "{raw_target}" за неделю'
        payload = {
            'rule_type': 'weekly_limit',
            'severity': 'hard',
            'name': title,
            'params_json': params
        }
        return payload, None

    # ── Шаблон 1.2: «две одинаковые тренировки в один день нельзя» ──
    duplicate_day_pattern = (
        ('одинаков' in src or 'дубликат' in src) and
        ('один день' in src or 'в один день' in src or 'за день' in src) and
        ('нельзя' in src or 'запрет' in src or 'не став' in src)
    )
    if duplicate_day_pattern:
        payload = {
            'rule_type': 'daily_duplicate_limit',
            'severity': 'hard',
            'name': 'Запрет одинаковых тренировок в день (утро/вечер)',
            'params_json': {
                'scope': 'bucket',
                'max_per_bucket_per_day': 1,
                'buckets': [
                    {'name': 'morning', 'start': '09:00', 'end': '14:00'},
                    {'name': 'evening', 'start': '16:00', 'end': '21:00'},
                ],
            }
        }
        return payload, None

    # ── Шаблон 2: «по понедельникам и средам можно 2 спокойные подряд» ──
    if 'спокойн' in src and 'подряд' in src and ('понедель' in src or 'сред' in src):
        weekdays = []
        for key, value in DAY_NAME_TO_INDEX.items():
            if key in src and value not in weekdays:
                weekdays.append(value)
        if not weekdays:
            weekdays = [0, 2]  # если дни не распознались — ставим пн и ср
        payload = {
            'rule_type': 'calm_consecutive',
            'severity': 'hard',
            'name': 'Спокойные подряд в выбранные дни',
            'params_json': {
                'weekdays': sorted(set(weekdays)),
                'max_consecutive': 2,
                'category': 'calm',
            }
        }
        return payload, None

    # ── Шаблон 2.1: «не ставь несколько силовых подряд» ──
    if 'силов' in src and 'подряд' in src:
        payload = {
            'rule_type': 'calm_consecutive',
            'severity': 'hard',
            'name': 'Запрет нескольких силовых подряд',
            'params_json': {
                'weekdays': [0, 1, 2, 3, 4, 5, 6],
                'max_consecutive': 1,
                'category': 'strength',
            }
        }
        return payload, None

    # ── Шаблон 3: «силовые и кардио должны чередоваться» ──
    if 'силов' in src and 'кардио' in src and ('черед' in src):
        payload = {
            'rule_type': 'alternation',
            'severity': 'hard',
            'name': 'Чередование силовых и кардио',
            'params_json': {
                'weekdays': [1, 3, 4, 5, 6],  # вт, чт, пт, сб, вс
                'categories': ['strength', 'cardio'],
                'mode': 'strict_alternate',
            }
        }
        return payload, None

    # ── Шаблон 3.1: «силовые и спокойные должны чередоваться» ──
    if 'силов' in src and 'спокой' in src and ('черед' in src):
        payload = {
            'rule_type': 'alternation',
            'severity': 'hard',
            'name': 'Чередование силовых и спокойных',
            'params_json': {
                'weekdays': [0, 1, 2, 3, 4, 5, 6],
                'categories': ['strength', 'calm'],
                'mode': 'strict_alternate',
            }
        }
        return payload, None

    # ── Шаблон 4: «не ставь две силовые подряд» ──
    if ('силов' in src or 'спокой' in src) and 'подряд' in src and ('не' in src or 'запрет' in src):
        cat = 'strength' if 'силов' in src else 'calm'
        payload = {
            'rule_type': 'calm_consecutive',
            'severity': 'hard',
            'name': f'Запрет нескольких {cat} подряд',
            'params_json': {
                'weekdays': [0, 1, 2, 3, 4, 5, 6],
                'max_consecutive': 1,
                'category': cat,
            }
        }
        return payload, None

    # ── Шаблон 5: «не более N раз в день» / «не чаще N раз в день» ──
    daily_limit = re.search(
        r'(?P<target>[а-яa-z0-9 \-_]+?)\s+.*?(?:не более|не чаще)\s+(?P<count>\d+)\s+раз.*?ден',
        src
    )
    if daily_limit:
        raw_target = daily_limit.group('target').strip(' "«»')
        count = int(daily_limit.group('count'))
        payload = {
            'rule_type': 'daily_duplicate_limit',
            'severity': 'hard',
            'name': f'Лимит {raw_target}: {count} в день',
            'params_json': {
                'scope': 'global',
                'max_per_bucket_per_day': count,
                'buckets': [
                    {'name': 'morning', 'start': '09:00', 'end': '14:00'},
                    {'name': 'evening', 'start': '16:00', 'end': '21:00'},
                ],
            }
        }
        return payload, None

    # ── Шаблон 6: «утром не более N» (только утро, без вечера) ──
    morning_only = re.search(
        r'(?P<target>[а-яa-z0-9 \-_]+?)\s+.*?утр.*?(?:не более|только)\s+(?P<count>\d+)',
        src
    )
    if morning_only:
        raw_target = morning_only.group('target').strip(' "«»')
        count = int(morning_only.group('count'))
        target_category = _extract_category_from_text(raw_target)
        params = {
            'period': 'week',
            'buckets': [
                {'name': 'morning', 'start': '09:00', 'end': '14:00', 'max': count},
            ],
        }
        if target_category:
            params.update({'target_mode': 'category', 'category': target_category})
            title = f'Лимит категории "{target_category}" утром'
        else:
            params.update({'target_mode': 'workout', 'workout_name': raw_target})
            title = f'Лимит "{raw_target}" утром'
        payload = {
            'rule_type': 'weekly_limit',
            'severity': 'hard',
            'name': title,
            'params_json': params
        }
        return payload, None

    return None, 'Не удалось распознать правило. Сейчас поддерживаются 4 шаблона из примеров.'


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
    rules = DistributionRule.objects.filter(is_active=True).order_by('priority', 'id')
    serialized = []
    for rule in rules:
        serialized.append({
            'id': rule.id,
            'name': rule.name,
            'rule_type': rule.rule_type,
            'severity': rule.severity,
            'params': rule.params_json or {},
        })
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
    """Создаёт строку-идентификатор временного окна (например, 'morning|09:00|14:00')."""
    return f"{(bucket or {}).get('name','')}|{(bucket or {}).get('start','')}|{(bucket or {}).get('end','')}"


def _extract_weekly_limit_map(rule: DistributionRule):
    """Извлекает из правила weekly_limit карту лимитов по временным окнам для сравнения."""
    if rule.rule_type != 'weekly_limit':
        return {}
    params = rule.params_json or {}
    target_mode = params.get('target_mode') or ('category' if params.get('category') else 'workout')
    target_key = (
        (params.get('category') or '').strip().lower()
        if target_mode == 'category'
        else _normalize_workout_name_for_rule(params.get('workout_name') or '')
    )
    if not target_key:
        return {}
    result = {}
    for bucket in (params.get('buckets') or []):
        try:
            max_value = int(bucket.get('max', 0))
        except Exception:
            max_value = 0
        result[_bucket_signature(bucket)] = {
            'max': max_value,
            'bucket': bucket,
            'target_mode': target_mode,
            'target_key': target_key,
        }
    return result


def _extract_alternation_signature(rule: DistributionRule):
    """Извлекает подпись чередования для сравнения двух alternation-правил."""
    if rule.rule_type != 'alternation':
        return None
    params = rule.params_json or {}
    categories = [str(x).strip().lower() for x in (params.get('categories') or []) if str(x).strip()]
    weekdays = sorted(set(int(x) for x in (params.get('weekdays') or []) if str(x).strip().isdigit()))
    if len(categories) < 2 or not weekdays:
        return None
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
    active_rules = [r for r in rules if r.is_active]
    conflicts = []

    for i in range(len(active_rules)):
        for j in range(i + 1, len(active_rules)):
            a = active_rules[i]
            b = active_rules[j]

            # 1) Явный конфликт: два weekly_limit на один target, одно окно, разные max
            a_week = _extract_weekly_limit_map(a)
            b_week = _extract_weekly_limit_map(b)
            if a_week and b_week:
                for bucket_key, a_data in a_week.items():
                    b_data = b_week.get(bucket_key)
                    if not b_data:
                        continue
                    if a_data['target_mode'] != b_data['target_mode'] or a_data['target_key'] != b_data['target_key']:
                        continue
                    if a_data['max'] != b_data['max']:
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
            a_alt = _extract_alternation_signature(a)
            b_alt = _extract_alternation_signature(b)
            if a_alt and b_alt:
                weekdays_intersection = set(a_alt['weekdays']) & set(b_alt['weekdays'])
                categories_intersection = set(a_alt['categories']) & set(b_alt['categories'])
                a_cnt = len(set(a_alt['categories']))
                b_cnt = len(set(b_alt['categories']))
                mixed_scope = (a_cnt >= 3 and b_cnt == 2) or (b_cnt >= 3 and a_cnt == 2)

                if (
                    weekdays_intersection
                    and categories_intersection
                    and set(a_alt['categories']) != set(b_alt['categories'])
                    and not mixed_scope
                ):
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
                if weekdays_intersection and ((a_cnt >= 3 and b_cnt == 2) or (b_cnt >= 3 and a_cnt == 2)):
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
            if a.rule_type == b.rule_type and a.severity == 'hard' and b.severity == 'hard':
                if a.rule_type == 'weekly_limit' and _extract_weekly_limit_map(a) and _extract_weekly_limit_map(b):
                    conflicts.append({
                        'level': 'soft',
                        'title': 'Перекрывающиеся жесткие weekly_limit',
                        'rule_a': a,
                        'rule_b': b,
                        'description': 'Два жестких weekly_limit могут дублировать друг друга и усложнять отладку.',
                        'how_to_fix': 'Объедините их в одно правило или понизьте жесткость/измените приоритет одного из них.',
                    })

    return conflicts


# ═══════════════════════════════════════════════════════════
# Страница правил распределения
# ═══════════════════════════════════════════════════════════

@login_required
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
    rules = DistributionRule.objects.all().select_related('created_by').order_by('priority', 'id')
    conflicts = _build_distribution_rules_conflicts(list(rules))
    conflict_rule_ids = set()
    conflict_rule_hard_ids = set()
    conflict_rule_soft_ids = set()
    for c in conflicts:
        level = c.get('level') or 'soft'
        if c.get('rule_a'):
            rid = c['rule_a'].id
            conflict_rule_ids.add(rid)
            if level == 'hard':
                conflict_rule_hard_ids.add(rid)
            else:
                conflict_rule_soft_ids.add(rid)
        if c.get('rule_b'):
            rid = c['rule_b'].id
            conflict_rule_ids.add(rid)
            if level == 'hard':
                conflict_rule_hard_ids.add(rid)
            else:
                conflict_rule_soft_ids.add(rid)
    conflict_rule_soft_ids = conflict_rule_soft_ids - conflict_rule_hard_ids
    return render(
        request,
        'core/schedules/distribution_rules.html',
        {
            'rules': rules,
            'rules_conflicts': conflicts,
            'rules_conflicts_count': len(conflicts),
            'conflict_rule_ids': sorted(conflict_rule_ids),
            'conflict_rule_hard_ids': sorted(conflict_rule_hard_ids),
            'conflict_rule_soft_ids': sorted(conflict_rule_soft_ids),
        }
    )


# ═══════════════════════════════════════════════════════════
# API: парсинг текста правила (ИИ → fallback-regex)
# ═══════════════════════════════════════════════════════════

@login_required
@user_passes_test(is_manager)
def api_parse_distribution_rule(request):
    """
    POST-эндпоинт для распознавания текста правила.

    Алгоритм:
      1. Пытаемся распознать через ИИ (try_parse_rule_with_ai)
      2. Если ИИ не справился — пробуем fallback-парсер (_parse_distribution_rule_text)
      3. Если оба не смогли — возвращаем ошибку

    Возвращает JSON с parsed (структура правила), source (ai/fallback_regex),
    explanation, confidence.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается.'}, status=405)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        payload = {}
    text = (payload.get('text') or '').strip()
    if not text:
        return JsonResponse({'success': False, 'error': 'Введите текст правила.'}, status=400)

    # Шаг 1: AI
    ai_result = try_parse_rule_with_ai(text)
    if ai_result.get('success'):
        return JsonResponse({
            'success': True,
            'parsed': ai_result['parsed'],
            'source': 'ai',
            'explanation': ai_result.get('explanation') or 'Распознано с помощью ИИ.',
            'confidence': ai_result.get('confidence', 0.85),
        })

    # Шаг 2: fallback-regex
    parsed, error = _parse_distribution_rule_text(text)
    if error:
        ai_error = ai_result.get('error')
        suffix = f" AI: {ai_error}" if ai_error else ""
        return JsonResponse({'success': False, 'error': f'{error}{suffix}'}, status=400)

    return JsonResponse({
        'success': True,
        'parsed': parsed,
        'source': 'fallback_regex',
        'explanation': 'Распознано резервным шаблонным парсером.',
        'confidence': 0.72,
    })


# ═══════════════════════════════════════════════════════════
# API: сохранение правила
# ═══════════════════════════════════════════════════════════

@login_required
@user_passes_test(is_manager)
def api_save_distribution_rule(request):
    """
    POST-эндпоинт для сохранения распознанного правила в БД.

    Принимает source_text (оригинальный текст) и parsed (распознанную структуру).
    Создаёт DistributionRule и проверяет конфликты с уже существующими правилами.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается.'}, status=405)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        payload = {}
    source_text = (payload.get('source_text') or '').strip()
    parsed = payload.get('parsed') or {}
    if not source_text:
        return JsonResponse({'success': False, 'error': 'Пустой текст правила.'}, status=400)
    if not parsed or not parsed.get('rule_type'):
        return JsonResponse({'success': False, 'error': 'Нет распознанных данных правила.'}, status=400)

    rule = DistributionRule.objects.create(
        name=(payload.get('name') or parsed.get('name') or source_text[:180]).strip()[:200],
        source_text=source_text,
        rule_type=parsed.get('rule_type'),
        severity=parsed.get('severity') if parsed.get('severity') in {'hard', 'soft'} else 'hard',
        params_json=parsed.get('params_json') or {},
        is_active=bool(payload.get('is_active', True)),
        priority=int(payload.get('priority', 100) or 100),
        created_by=request.user,
    )
    conflicts = _build_distribution_rules_conflicts(
        list(DistributionRule.objects.all().order_by('priority', 'id'))
    )
    return JsonResponse({
        'success': True,
        'rule_id': rule.id,
        'conflicts_count': len(conflicts),
    })


# ═══════════════════════════════════════════════════════════
# API: включение/выключение правила
# ═══════════════════════════════════════════════════════════

@login_required
@user_passes_test(is_manager)
def api_toggle_distribution_rule(request, rule_id):
    """Переключает is_active у правила (вкл/выкл) без удаления."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается.'}, status=405)
    rule = get_object_or_404(DistributionRule, id=rule_id)
    rule.is_active = not rule.is_active
    rule.save(update_fields=['is_active', 'updated_at'])
    return JsonResponse({'success': True, 'is_active': rule.is_active})


# ═══════════════════════════════════════════════════════════
# API: удаление правила
# ═══════════════════════════════════════════════════════════

@login_required
@user_passes_test(is_manager)
def api_delete_distribution_rule(request, rule_id):
    """Полностью удаляет правило распределения из БД."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается.'}, status=405)
    rule = get_object_or_404(DistributionRule, id=rule_id)
    rule.delete()
    return JsonResponse({'success': True})


# ═══════════════════════════════════════════════════════════
# API: обновление правила (название, жёсткость, приоритет)
# ═══════════════════════════════════════════════════════════

@login_required
@user_passes_test(is_manager)
def api_update_distribution_rule(request, rule_id):
    """Обновляет название, жёсткость и приоритет существующего правила."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается.'}, status=405)
    rule = get_object_or_404(DistributionRule, id=rule_id)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        payload = {}

    name = (payload.get('name') or '').strip()
    severity = (payload.get('severity') or '').strip()
    priority_raw = payload.get('priority', rule.priority)

    if name:
        rule.name = name[:200]
    if severity in {'hard', 'soft'}:
        rule.severity = severity
    try:
        rule.priority = max(1, int(priority_raw))
    except Exception:
        pass

    rule.save(update_fields=['name', 'severity', 'priority', 'updated_at'])
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
    n = (workout_name or '').lower()
    if any(x in n for x in ['табата', 'кардио', 'cardio', 'hiit']):
        return 'cardio'
    if any(x in n for x in ['сил', 'strength', 'power']):
        return 'strength'
    if any(x in n for x in ['dance', 'танц', 'bachata', 'восточ', 'стрип']):
        return 'dance'
    if any(x in n for x in ['stretch', 'растяж', 'йог', 'calm', 'спокой']):
        return 'calm'
    return 'other'


def _normalize_workout_name_for_rule(name: str) -> str:
    """
    Приводит название тренировки к канонической форме для сравнения.

    Нужно, чтобы «табата» и «tabata» считались одним и тем же направлением.
    """
    n = (name or '').strip().lower()
    aliases = {
        'табата': 'tabata',
        'стретчинг': 'stretching',
        'растяжка': 'stretching',
        'бачата': 'bachata',
        'силовые': 'strength',
        'кардио': 'cardio',
    }
    return aliases.get(n, n)


def _time_in_bucket(start_time, bucket):
    """Проверяет, попадает ли время начала занятия в заданное окно (утро/вечер)."""
    st = start_time.strftime('%H:%M')
    return (bucket.get('start') or '00:00') <= st < (bucket.get('end') or '23:59')


# ═══════════════════════════════════════════════════════════
# API: тестирование правил на существующих графиках
# ═══════════════════════════════════════════════════════════

@login_required
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
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается.'}, status=405)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        payload = {}

    start_raw = (payload.get('start_date') or '').strip()
    end_raw = (payload.get('end_date') or '').strip()
    if not start_raw or not end_raw:
        return JsonResponse({'success': False, 'error': 'Укажите период.'}, status=400)
    try:
        start_date = datetime.strptime(start_raw, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_raw, '%Y-%m-%d').date()
    except Exception:
        return JsonResponse({'success': False, 'error': 'Некорректный формат даты.'}, status=400)
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    rules = list(DistributionRule.objects.filter(is_active=True).order_by('priority', 'id'))
    assignments = list(
        ShiftAssignment.objects.filter(
            date__gte=start_date,
            date__lte=end_date,
            workout_type__isnull=False,
        ).select_related('workout_type', 'employee__user')
    )
    assignments.sort(key=lambda a: (a.date, a.start_time))

    violations = []
    weekly_counts = {}         # weekly bucket: сколько уже поставили
    weekly_total_counts = {}   # weekly total: общее количество за неделю
    daily_bucket_workout_counts = {}  # daily: сколько одинаковых в одном окне
    calm_streaks = {}          # consecutive: streak подряд
    prev_category = {}         # alternation: какая категория была последней

    for a in assignments:
        workout_name = a.workout_type.name if a.workout_type_id else ''
        category = (
            a.workout_type.category
            if getattr(a.workout_type, 'category', None)
            else _infer_category_from_name(workout_name)
        )
        weekday = a.date.weekday()
        day_key = a.date.isoformat()
        week_key = f"{a.date.isocalendar().year}-{a.date.isocalendar().week}"

        for rule in rules:
            params = rule.params_json or {}

            # ── weekly_limit: лимит на неделю ──
            if rule.rule_type == 'weekly_limit':
                target_mode = params.get('target_mode') or (
                    'category' if params.get('category') else 'workout'
                )
                target_workout = _normalize_workout_name_for_rule(params.get('workout_name') or '')
                target_category = (params.get('category') or '').strip()
                workout_norm = _normalize_workout_name_for_rule(workout_name)
                # Определяем, подходит ли это назначение под проверяемое правило
                is_match = False
                if target_mode == 'category':
                    is_match = bool(target_category and category == target_category)
                else:
                    is_match = bool(target_workout and target_workout in workout_norm)

                if is_match:
                    # Проверка общего лимита (max_total)
                    total_key = f"{rule.id}|{week_key}|total"
                    weekly_total_counts[total_key] = weekly_total_counts.get(total_key, 0) + 1
                    if params.get('max_total') is not None and weekly_total_counts[total_key] > int(params.get('max_total', 0)):
                        violations.append({
                            'rule': rule.name,
                            'date': a.date.strftime('%d.%m.%Y'),
                            'time': a.start_time.strftime('%H:%M'),
                            'workout': workout_name,
                            'employee': a.employee.user.username,
                            'reason': 'Превышен общий недельный лимит',
                        })

                    # Проверка лимитов по временным окнам (утро/вечер)
                    for b in (params.get('buckets') or []):
                        if _time_in_bucket(a.start_time, b):
                            key = f"{rule.id}|{week_key}|{b.get('name','bucket')}"
                            weekly_counts[key] = weekly_counts.get(key, 0) + 1
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
            elif rule.rule_type == 'calm_consecutive':
                weekdays = params.get('weekdays') or []
                max_consecutive = int(params.get('max_consecutive', 2))
                expected = params.get('category', 'calm')
                if weekday in weekdays:
                    if category == expected:
                        # Увеличиваем счётчик подряд
                        calm_streaks[day_key] = calm_streaks.get(day_key, 0) + 1
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
            elif rule.rule_type == 'alternation':
                weekdays = params.get('weekdays') or []
                categories = params.get('categories') or ['strength', 'cardio']
                if weekday in weekdays and category in categories:
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
                    prev_category[day_key] = category

            # ── daily_duplicate_limit: запрет дублей в день ──
            elif rule.rule_type == 'daily_duplicate_limit':
                buckets = params.get('buckets') or []
                max_per_bucket_per_day = int(params.get('max_per_bucket_per_day', 1))
                workout_norm = _normalize_workout_name_for_rule(workout_name)
                for b in buckets:
                    if _time_in_bucket(a.start_time, b):
                        key = f"{rule.id}|{day_key}|{b.get('name','bucket')}|{workout_norm}"
                        daily_bucket_workout_counts[key] = daily_bucket_workout_counts.get(key, 0) + 1
                        if daily_bucket_workout_counts[key] > max_per_bucket_per_day:
                            violations.append({
                                'rule': rule.name,
                                'date': a.date.strftime('%d.%m.%Y'),
                                'time': a.start_time.strftime('%H:%M'),
                                'workout': workout_name,
                                'employee': a.employee.user.username,
                                'reason': 'Одинаковая тренировка повторяется в одном окне дня',
                            })

    return JsonResponse({
        'success': True,
        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
        },
        'rules_count': len(rules),
        'violations_count': len(violations),
        'violations': violations[:150],  # Ограничиваем вывод, чтобы не сломать JSON
    })
