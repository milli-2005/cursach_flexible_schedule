"""Интеграция с AI-парсером, который превращает текст правила распределения в структурированные параметры."""

import json
import logging
from typing import Any, Dict, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)

SUPPORTED_RULE_TYPES = {"weekly_limit", "calm_consecutive", "alternation", "daily_duplicate_limit"}
SUPPORTED_SEVERITY = {"hard", "soft"}
SUPPORTED_CATEGORIES = {"calm", "cardio", "strength", "dance", "other"}

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

EXAMPLES = [
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
]


def _build_prompt(rule_text: str) -> str:
    """Собирает промпт для AI-модели, чтобы она распознала правило распределения."""
    prompt = SYSTEM_PROMPT + "\n\nПримеры:\n"
    for ex in EXAMPLES:
        prompt += f"\nТекст: {ex['text']}\nJSON: {json.dumps(ex['json'], ensure_ascii=False)}\n"
    prompt += f"\n\nТекст правила: {rule_text}\n\nJSON:"
    return prompt


def _validate_ai_result(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """Проверяет, что ответ AI содержит нужные поля и безопасен для сохранения."""
    if payload.get("need_clarification") is True:
        return False, payload.get("error") or "Нужно уточнение правила."

    rule_type = payload.get("rule_type")
    severity = payload.get("severity")
    params = payload.get("params_json")

    if rule_type not in SUPPORTED_RULE_TYPES:
        return False, "AI вернул неподдерживаемый тип правила."
    if severity not in SUPPORTED_SEVERITY:
        return False, "AI вернул неподдерживаемую жесткость."
    if not isinstance(params, dict):
        return False, "AI вернул некорректные параметры правила."

    if rule_type == "weekly_limit":
        target_mode = params.get("target_mode") or ("category" if params.get("category") else "workout")
        if target_mode not in {"workout", "category"}:
            return False, "Для weekly_limit target_mode должен быть workout или category."
        if target_mode == "workout" and not params.get("workout_name"):
            return False, "Для weekly_limit (workout) не задан workout_name."
        if target_mode == "category":
            cat = params.get("category")
            if cat not in SUPPORTED_CATEGORIES:
                return False, "Для weekly_limit (category) не задана корректная category."
        has_buckets = isinstance(params.get("buckets"), list) and bool(params.get("buckets"))
        has_max_total = params.get("max_total") is not None
        if not has_buckets and not has_max_total:
            return False, "Для weekly_limit задайте либо buckets, либо max_total."

    elif rule_type == "calm_consecutive":
        if not isinstance(params.get("weekdays"), list):
            return False, "Для calm_consecutive не заданы weekdays."
        if not isinstance(params.get("max_consecutive"), int):
            return False, "Для calm_consecutive не задан max_consecutive."
        if params.get("category") not in SUPPORTED_CATEGORIES:
            return False, "Для calm_consecutive не задана корректная category."

    elif rule_type == "alternation":
        if not isinstance(params.get("weekdays"), list):
            return False, "Для alternation не заданы weekdays."
        categories = params.get("categories")
        if not isinstance(categories, list) or len(categories) < 2:
            return False, "Для alternation не заданы categories."
        for cat in categories:
            if cat not in SUPPORTED_CATEGORIES:
                return False, "Для alternation указана некорректная category."

    elif rule_type == "daily_duplicate_limit":
        if not isinstance(params.get("buckets"), list) or not params.get("buckets"):
            return False, "Для daily_duplicate_limit не заданы buckets."
        if not isinstance(params.get("max_per_bucket_per_day"), int):
            return False, "Для daily_duplicate_limit не задан max_per_bucket_per_day."

    return True, ""


def try_parse_rule_with_ai(rule_text: str, retry: bool = True):
    """Пытается распознать правило через AI с двумя попытками."""
    if not getattr(settings, "RULE_AI_ENABLED", False):
        return {"success": False, "error": "AI отключен в настройках.", "source": "ai"}

    api_key = getattr(settings, "OPENAI_API_KEY", "")
    model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
    if not api_key:
        return {"success": False, "error": "Не задан OPENAI_API_KEY.", "source": "ai"}

    try:
        from openai import OpenAI
    except Exception as exc:
        logger.warning("OpenAI package import failed: %s", exc)
        return {"success": False, "error": "Пакет openai не установлен.", "source": "ai"}

    prompt = _build_prompt(rule_text)
    attempts = [prompt]
    if retry:
        simplified = (
            f"Определи правило распределения для текста: «{rule_text}»\n"
            "Верни JSON с rule_type, severity, name, params_json, explanation, confidence.\n"
            "Если не получается — верни need_clarification: true."
        )
        attempts.append(simplified)

    for i, current_prompt in enumerate(attempts):
        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": current_prompt},
                    {"role": "user", "content": rule_text},
                ],
                temperature=0,
                max_tokens=1000,
            )
            text = (response.choices[0].message.content or "").strip()
            if not text:
                continue

            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            payload = json.loads(text)
            ok, error = _validate_ai_result(payload)
            if ok:
                confidence = payload.get("confidence", 0.85)
                try:
                    confidence = float(confidence)
                except Exception:
                    confidence = 0.85
                confidence = max(0.0, min(1.0, confidence))

                return {
                    "success": True,
                    "parsed": payload,
                    "source": "ai",
                    "explanation": payload.get("explanation") or "Распознано по семантике текста.",
                    "confidence": confidence,
                }
        except Exception as exc:
            logger.warning("AI parse attempt %d failed: %s", i + 1, exc)

    return {"success": False, "error": "AI не смог распознать правило после нескольких попыток.", "source": "ai"}
