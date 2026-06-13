"""Интеграция с AI-парсером, который пытается превратить текст правила в структурированные параметры."""

import json
import logging
from typing import Any, Dict, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)


SUPPORTED_RULE_TYPES = {"weekly_limit", "calm_consecutive", "alternation", "daily_duplicate_limit"}
SUPPORTED_SEVERITY = {"hard", "soft"}
SUPPORTED_CATEGORIES = {"calm", "cardio", "strength", "dance", "other"}


def _build_prompt(rule_text: str) -> str:
    """Собирает промпт для AI-модели, чтобы она распознала правило распределения."""
    schema = {
        "rule_type": "weekly_limit | calm_consecutive | alternation | daily_duplicate_limit",
        "severity": "hard | soft",
        "name": "Короткое понятное название правила",
        "params_json": {
            "depends_on_rule_type": "см. примеры",
            "target_mode": "workout | category (для weekly_limit)"
        },
        "explanation": "Почему выбран такой тип и параметры",
        "confidence": "Число от 0 до 1",
    }

    examples = [
        {
            "text": "Табата не более 1 раза утром и 1 раза вечером в неделю",
            "json": {
                "rule_type": "weekly_limit",
                "severity": "hard",
                "name": "Лимит tabata по неделе",
                "params_json": {
                    "target_mode": "workout",
                    "workout_name": "tabata",
                    "period": "week",
                    "buckets": [
                        {"name": "morning", "start": "09:00", "end": "14:00", "max": 1},
                        {"name": "evening", "start": "16:00", "end": "21:00", "max": 1},
                    ],
                },
                "explanation": "Недельный лимит для конкретного направления с окнами утро/вечер.",
                "confidence": 0.98,
            },
        },
        {
            "text": "Кардио не более 5 раз в неделю",
            "json": {
                "rule_type": "weekly_limit",
                "severity": "hard",
                "name": "Лимит категории cardio",
                "params_json": {
                    "target_mode": "category",
                    "category": "cardio",
                    "period": "week",
                    "max_total": 5,
                },
                "explanation": "Недельный лимит по категории, не по названию занятия.",
                "confidence": 0.96,
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
                "explanation": "Чередование двух категорий.",
                "confidence": 0.95,
            },
        },
    ]

    return (
        "Ты преобразуешь правило распределения расписания в JSON.\n"
        "Верни только JSON без markdown.\n"
        "Если распознать нельзя — верни JSON: "
        '{"need_clarification": true, "error": "...", "explanation":"...", "confidence":0.0}\n'
        f"Схема: {json.dumps(schema, ensure_ascii=False)}\n"
        f"Примеры: {json.dumps(examples, ensure_ascii=False)}\n"
        f"Правило: {rule_text}"
    )


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


def try_parse_rule_with_ai(rule_text: str):
    """Пытается распознать правило через AI и возвращает результат без падения страницы."""
    if not getattr(settings, "RULE_AI_ENABLED", False):
        return {"success": False, "error": "AI отключен в настройках.", "source": "ai"}

    api_key = getattr(settings, "OPENAI_API_KEY", "")
    model = getattr(settings, "OPENAI_MODEL", "gpt-5.4-mini")
    if not api_key:
        return {"success": False, "error": "Не задан OPENAI_API_KEY.", "source": "ai"}

    try:
        from openai import OpenAI
    except Exception as exc:
        logger.warning("OpenAI package import failed: %s", exc)
        return {"success": False, "error": "Пакет openai не установлен.", "source": "ai"}

    prompt = _build_prompt(rule_text)
    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model,
            input=prompt,
            temperature=0,
        )
        text = (response.output_text or "").strip()
        if not text:
            return {"success": False, "error": "AI вернул пустой ответ.", "source": "ai"}

        payload = json.loads(text)
        ok, error = _validate_ai_result(payload)
        if not ok:
            return {"success": False, "error": error, "source": "ai"}

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
        logger.warning("AI parse failed: %s", exc)
        return {"success": False, "error": f"Ошибка AI: {exc}", "source": "ai"}
