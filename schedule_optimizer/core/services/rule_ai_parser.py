# ============================================================
# Интеграция с AI-парсером правил распределения занятий
# ============================================================
# Этот модуль отвечает за распознавание текстовых правил,
# которые менеджер вводит на русском языке, в структурированные
# JSON-параметры для алгоритма автозаполнения графика.
#
# Алгоритм:
#   1. Собирает промпт с примерами (few-shot) для AI-модели
#   2. Отправляет запрос к OpenAI (gpt-4o-mini)
#   3. Валидирует ответ — проверяет типы правил и параметры
#   4. Если AI недоступен — возвращает ошибку (fallback в distribution_rules.py)
# ============================================================

import json  # Для парсинга JSON-ответа от AI
import logging  # Логирование ошибок и предупреждений
from typing import Any, Dict, Tuple  # Аннотации типов

from django.conf import settings  # Доступ к настройкам проекта (API-ключ, модель)

# Настройка логгера для этого модуля
logger = logging.getLogger(__name__)

# ============================================================
# Константы-валидаторы
# ============================================================
# Список поддерживаемых типов правил
# weekly_limit      — недельный лимит (N раз в неделю)
# calm_consecutive  — лимит спокойных подряд
# alternation       — чередование категорий
# daily_duplicate_limit — запрет дублей в день
SUPPORTED_RULE_TYPES = {"weekly_limit", "calm_consecutive", "alternation", "daily_duplicate_limit"}

# Допустимые значения жёсткости правила
# hard  — жёсткое (нарушение = ошибка автозаполнения)
# soft  — мягкое (рекомендация)
SUPPORTED_SEVERITY = {"hard", "soft"}

# Допустимые категории тренировок
SUPPORTED_CATEGORIES = {"calm", "cardio", "strength", "dance", "other"}

# ============================================================
# Системный промпт для AI-модели
# ============================================================
# Это инструкция, которая отправляется модели перед текстом правила.
# Описывает типы правил, формат JSON и требования к валидации.
SYSTEM_PROMPT = """Ты — помощник, который преобразует правила распределения расписания тренировок в JSON.

Правила задаются на русском языке менеджером фитнес-клуба. Тебе нужно понять тип правила и извлечь параметры.

Доступные типы правил:
1. weekly_limit — недельный лимит на количество тренировок (по названию или категории)
2. calm_consecutive — сколько спокойных тренировок может быть подряд
3. alternation — чередование категорий тренировок
4. daily_duplicate_limit — ограничение на одинаковые тренировки в день

Категории тренировок: calm (спокойные/йога/стретч/растяжка), cardio (кардио), strength (силовые), dance (танцы), other (другое)

Верни ТОЛЬКО JSON без markdown-разметки и без пояснений.
Если не уверен — верни JSON с need_clarification: true и объяснением почему.

Проверь что:
- Для weekly_limit указан хотя бы один из: buckets (массив с max) ИЛИ max_total
- Для alternation указаны минимум 2 категории в categories
- Для calm_consecutive указан max_consecutive
- Для daily_duplicate_limit указан max_per_bucket_per_day
- Все названия тренировок (workout_name) на русском языке
- Дни недели: 0=пн, 1=вт, 2=ср, 3=чт, 4=пт, 5=сб, 6=вс"""

# ============================================================
# Примеры для few-shot обучения (примеры → JSON)
# ============================================================
# Каждый пример содержит:
#   text — исходный текст правила на русском
#   json — ожидаемый JSON-ответ от модели
#
# Это помогает модели понять формат без дополнительных инструкций.
EXAMPLES = [
    # Пример 1: лимит по времени (утро/вечер) для конкретного занятия
    {
        "text": "Табата не более 1 раза утром и 1 раза вечером в неделю",
        "json": {
            "rule_type": "weekly_limit",
            "severity": "hard",
            "name": "Лимит табата: 1 утром + 1 вечером",
            "params_json": {
                "target_mode": "workout",
                "workout_name": "табата",
                "period": "week",
                "buckets": [
                    {"name": "morning", "start": "09:00", "end": "14:00", "max": 1},
                    {"name": "evening", "start": "16:00", "end": "21:00", "max": 1},
                ],
            },
            "explanation": "Недельный лимит для табаты: утром (9-14) не больше 1, вечером (16-21) не больше 1",
            "confidence": 0.98,
        },
    },
    # Пример 2: лимит по категории за неделю (max_total)
    {
        "text": "Кардио не более 5 раз в неделю",
        "json": {
            "rule_type": "weekly_limit",
            "severity": "hard",
            "name": "Лимит кардио: 5 в неделю",
            "params_json": {
                "target_mode": "category",
                "category": "cardio",
                "period": "week",
                "max_total": 5,
            },
            "explanation": "Недельный лимит по категории cardio",
            "confidence": 0.97,
        },
    },
    # Пример 3: лимит по названию за неделю
    {
        "text": "Сайкл не чаще 3 раз за неделю",
        "json": {
            "rule_type": "weekly_limit",
            "severity": "hard",
            "name": "Лимит сайкл: 3 в неделю",
            "params_json": {
                "target_mode": "workout",
                "workout_name": "сайкл",
                "period": "week",
                "max_total": 3,
            },
            "explanation": "Недельный лимит для сайкла",
            "confidence": 0.96,
        },
    },
    # Пример 4: дневной лимит (не более N в день)
    {
        "text": "Йога не более 2 раз в день",
        "json": {
            "rule_type": "daily_duplicate_limit",
            "severity": "hard",
            "name": "Лимит йоги: 2 в день",
            "params_json": {
                "scope": "global",
                "max_per_bucket_per_day": 2,
                "buckets": [
                    {"name": "morning", "start": "09:00", "end": "14:00"},
                    {"name": "evening", "start": "16:00", "end": "21:00"},
                ],
            },
            "explanation": "Дневной лимит для йоги: не более 2 тренировок в день",
            "confidence": 0.95,
        },
    },
    # Пример 5: чередование двух категорий
    {
        "text": "Силовые и спокойные должны чередоваться",
        "json": {
            "rule_type": "alternation",
            "severity": "hard",
            "name": "Чередование силовых и спокойных",
            "params_json": {
                "weekdays": [0, 1, 2, 3, 4, 5, 6],
                "categories": ["strength", "calm"],
                "mode": "strict_alternate",
            },
            "explanation": "Силовые и спокойные тренировки должны строго чередоваться",
            "confidence": 0.95,
        },
    },
    # Пример 6: лимит спокойных подряд
    {
        "text": "Стретч не ставить больше 2 раз подряд",
        "json": {
            "rule_type": "calm_consecutive",
            "severity": "soft",
            "name": "Не более 2 спокойных подряд",
            "params_json": {
                "weekdays": [0, 1, 2, 3, 4, 5, 6],
                "max_consecutive": 2,
                "category": "calm",
            },
            "explanation": "Спокойные тренировки не более 2 подряд в любой день",
            "confidence": 0.93,
        },
    },
    # Пример 7: утренний лимит на конкретное занятие
    {
        "text": "Пилатес утром не чаще 1 раза",
        "json": {
            "rule_type": "weekly_limit",
            "severity": "hard",
            "name": "Лимит пилатеса утром",
            "params_json": {
                "target_mode": "workout",
                "workout_name": "пилатес",
                "period": "week",
                "buckets": [
                    {"name": "morning", "start": "09:00", "end": "14:00", "max": 1},
                ],
            },
            "explanation": "Пилатес утром не чаще 1 раза в неделю",
            "confidence": 0.94,
        },
    },
    # Пример 8: запрет дубликатов по дням недели
    {
        "text": "В понедельник и пятницу не должно быть двух одинаковых тренировок",
        "json": {
            "rule_type": "daily_duplicate_limit",
            "severity": "hard",
            "name": "Запрет дубликатов в пн и пт",
            "params_json": {
                "scope": "global",
                "max_per_bucket_per_day": 1,
                "weekdays": [0, 4],
                "buckets": [
                    {"name": "morning", "start": "09:00", "end": "14:00"},
                    {"name": "evening", "start": "16:00", "end": "21:00"},
                ],
            },
            "explanation": "В понедельник и пятницу нельзя ставить две одинаковые тренировки в один день",
            "confidence": 0.92,
        },
    },
    # Пример 9: запрет дублей у одного тренера за смену
    {
        "text": "у одного тренера не может быть одинаковых тренировок за смену",
        "json": {
            "rule_type": "daily_duplicate_limit",
            "severity": "hard",
            "name": "Запрет одинаковых тренировок за смену",
            "params_json": {
                "scope": "trainer",
                "max_per_bucket_per_day": 1,
                "buckets": [
                    {"name": "morning", "start": "09:00", "end": "14:00"},
                    {"name": "evening", "start": "16:00", "end": "21:00"},
                ],
            },
            "explanation": "У одного тренера за смену не может быть двух одинаковых тренировок",
            "confidence": 0.95,
        },
    },
]


# ============================================================
# Сборка промпта
# ============================================================
def _build_prompt(rule_text: str) -> str:
    """
    Собирает промпт для AI-модели.
    Берёт system-инструкцию, добавляет примеры и текст правила.
    """
    # Начинаем с системной инструкции
    prompt = SYSTEM_PROMPT + "\n\nПримеры:\n"
    # Добавляем каждый пример как пару "текст → JSON"
    for ex in EXAMPLES:
        prompt += f"\nТекст: {ex['text']}\nJSON: {json.dumps(ex['json'], ensure_ascii=False)}\n"
    # Добавляем текст, который нужно распознать
    prompt += f"\n\nТекст правила: {rule_text}\n\nJSON:"
    return prompt


# ============================================================
# Валидация ответа AI
# ============================================================
def _validate_ai_result(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Проверяет JSON-ответ от AI на корректность.
    Возвращает (True, '') если всё ок, или (False, 'ошибка') если нет.

    Проверяет:
      - Наличие обязательных полей
      - Тип правила из списка SUPPORTED_RULE_TYPES
      - Жёсткость из SUPPORTED_SEVERITY
      - category из SUPPORTED_CATEGORIES
      - Специфичные для каждого типа правила поля
    """
    # Если AI запросил уточнение — возвращаем ошибку
    if payload.get("need_clarification") is True:
        return False, payload.get("error") or "Нужно уточнение правила."

    # Извлекаем основные поля
    rule_type = payload.get("rule_type")  # Тип правила (weekly_limit, alternation, ...)
    severity = payload.get("severity")    # Жёсткость (hard, soft)
    params = payload.get("params_json")   # Параметры (структура зависит от типа)

    # Проверка базовых полей
    if rule_type not in SUPPORTED_RULE_TYPES:
        return False, "AI вернул неподдерживаемый тип правила."
    if severity not in SUPPORTED_SEVERITY:
        return False, "AI вернул неподдерживаемую жесткость."
    if not isinstance(params, dict):
        return False, "AI вернул некорректные параметры правила."

    # Валидация для weekly_limit — недельный лимит
    if rule_type == "weekly_limit":
        # Определяем режим: по названию тренировки или по категории
        target_mode = params.get("target_mode") or ("category" if params.get("category") else "workout")
        if target_mode not in {"workout", "category"}:
            return False, "Для weekly_limit target_mode должен быть workout или category."
        if target_mode == "workout" and not params.get("workout_name"):
            # Если лимит по названию — нужно имя тренировки
            return False, "Для weekly_limit (workout) не задан workout_name."
        if target_mode == "category":
            cat = params.get("category")
            if cat not in SUPPORTED_CATEGORIES:
                return False, "Для weekly_limit (category) не задана корректная category."
        # Должен быть хотя бы один из: buckets (массив окон) ИЛИ max_total
        has_buckets = isinstance(params.get("buckets"), list) and bool(params.get("buckets"))
        has_max_total = params.get("max_total") is not None
        if not has_buckets and not has_max_total:
            return False, "Для weekly_limit задайте либо buckets, либо max_total."

    # Валидация для calm_consecutive — лимит спокойных подряд
    elif rule_type == "calm_consecutive":
        if not isinstance(params.get("weekdays"), list):
            return False, "Для calm_consecutive не заданы weekdays."
        if not isinstance(params.get("max_consecutive"), int):
            return False, "Для calm_consecutive не задан max_consecutive."
        if params.get("category") not in SUPPORTED_CATEGORIES:
            return False, "Для calm_consecutive не задана корректная category."

    # Валидация для alternation — чередование категорий
    elif rule_type == "alternation":
        if not isinstance(params.get("weekdays"), list):
            return False, "Для alternation не заданы weekdays."
        categories = params.get("categories")
        if not isinstance(categories, list) or len(categories) < 2:
            # Нужно минимум 2 категории для чередования
            return False, "Для alternation не заданы categories."
        for cat in categories:
            if cat not in SUPPORTED_CATEGORIES:
                return False, "Для alternation указана некорректная category."

    # Валидация для daily_duplicate_limit — запрет дублей в день
    elif rule_type == "daily_duplicate_limit":
        if not isinstance(params.get("buckets"), list) or not params.get("buckets"):
            return False, "Для daily_duplicate_limit не заданы buckets."
        if not isinstance(params.get("max_per_bucket_per_day"), int):
            return False, "Для daily_duplicate_limit не задан max_per_bucket_per_day."

    # Все проверки пройдены — ответ валиден
    return True, ""


# ============================================================
# Основная функция: попытка распознать правило через AI
# ============================================================
def try_parse_rule_with_ai(rule_text: str, retry: bool = True):
    """
    Пытается распознать правило через AI с возможностью повторной попытки.

    Аргументы:
      rule_text — текст правила на русском (например, «Табата не чаще 1 раза утром»)
      retry     — если True, при неудаче делает вторую попытку с упрощённым промптом

    Возвращает словарь:
      success: True/False
      parsed:  распознанная структура (если success)
      error:   сообщение об ошибке (если не success)
      source:  всегда 'ai'
      explanation: пояснение от AI
      confidence:  уверенность AI (0..1)

    Алгоритм:
      1. Проверяет, включён ли AI в настройках (RULE_AI_ENABLED)
      2. Проверяет наличие API-ключа OpenAI
      3. Импортирует openai (если пакет не установлен — ошибка)
      4. Собирает промпт через _build_prompt()
      5. Пробует отправить запрос (с повторной попыткой при необходимости)
      6. Валидирует ответ через _validate_ai_result()
      7. Возвращает результат или ошибку
    """
    # Проверка: включён ли AI в настройках Django
    if not getattr(settings, "RULE_AI_ENABLED", False):
        return {"success": False, "error": "AI отключен в настройках.", "source": "ai"}

    # Получаем настройки OpenAI из конфигурации Django
    api_key = getattr(settings, "OPENAI_API_KEY", "")       # Ключ API
    model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")  # Модель (по умолчанию gpt-4o-mini)
    base_url = getattr(settings, "OPENAI_BASE_URL", None)    # Кастомный endpoint (если есть прокси)
    if not api_key:
        # Ключ не задан — AI недоступен
        return {"success": False, "error": "Не задан OPENAI_API_KEY.", "source": "ai"}

    # Импортируем openai — если пакет не установлен, возвращаем ошибку
    try:
        from openai import OpenAI
    except Exception as exc:
        logger.warning("OpenAI package import failed: %s", exc)
        return {"success": False, "error": "Пакет openai не установлен.", "source": "ai"}

    # Собираем промпт с примерами
    prompt = _build_prompt(rule_text)

    # Список попыток: сначала полный промпт, потом (если retry) упрощённый
    attempts = [prompt]
    if retry:
        # Упрощённый промпт без примеров — на случай, если модель не справилась с полным
        simplified = (
            f"Определи правило распределения для текста: «{rule_text}»\n"
            "Верни JSON с rule_type, severity, name, params_json, explanation, confidence.\n"
            "Если не получается — верни need_clarification: true."
        )
        attempts.append(simplified)

    # Проходим по попыткам
    for i, current_prompt in enumerate(attempts):
        try:
            # Создаём клиента OpenAI с переданными настройками
            client_kwargs = {"api_key": api_key}
            if base_url:
                # Если указан кастомный base_url (например, для прокси/прокта)
                client_kwargs["base_url"] = base_url
            client = OpenAI(**client_kwargs)

            # Отправляем запрос к chat completion API
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": current_prompt},  # Системный промпт с инструкцией
                    {"role": "user", "content": rule_text},          # Текст правила от пользователя
                ],
                temperature=0,       # Минимум случайности — детерминированный ответ
                max_tokens=1000,     # Ограничение длины ответа
            )

            # Извлекаем текст ответа
            text = (response.choices[0].message.content or "").strip()
            if not text:
                # Пустой ответ — пробуем следующую попытку
                continue

            # Очищаем от markdown-разметки (```json ... ```)
            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            # Парсим JSON
            payload = json.loads(text)

            # Валидируем ответ
            ok, error = _validate_ai_result(payload)
            if ok:
                # Ответ валиден — извлекаем confidence (уверенность)
                confidence = payload.get("confidence", 0.85)
                try:
                    confidence = float(confidence)
                except Exception:
                    confidence = 0.85
                # Нормализуем к диапазону [0, 1]
                confidence = max(0.0, min(1.0, confidence))

                # Возвращаем успешный результат
                return {
                    "success": True,
                    "parsed": payload,  # Распознанная структура правила
                    "source": "ai",
                    "explanation": payload.get("explanation") or "Распознано по семантике текста.",
                    "confidence": confidence,
                }

        except Exception as exc:
            # Логируем ошибку и пробуем следующую попытку
            logger.warning("AI parse attempt %d failed: %s", i + 1, exc)

    # Все попытки исчерпаны — возвращаем ошибку
    return {"success": False, "error": "AI не смог распознать правило после нескольких попыток.", "source": "ai"}
