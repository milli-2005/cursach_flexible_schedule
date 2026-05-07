import json
import logging
from typing import Any, Dict, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)


def _build_prompt(rule_text: str) -> str:
    schema = {
        "rule_type": "weekly_limit | calm_consecutive | alternation | daily_duplicate_limit",
        "severity": "hard | soft",
        "name": "Короткое название правила",
        "params_json": {"depends_on_rule_type": "см. примеры ниже"},
        "explanation": "Почему ИИ выбрал именно такой тип и параметры",
        "confidence": "Число от 0 до 1",
    }
    examples = [
        {
            "text": "Табата не более 1 раза утром и 1 раза вечером в неделю",
            "json": {
                "rule_type": "weekly_limit",
                "severity": "hard",
                "name": 'Лимит "табата" по неделе',
                "params_json": {
                    "workout_name": "табата",
                    "period": "week",
                    "buckets": [
                        {"name": "morning", "start": "09:00", "end": "14:00", "max": 1},
                        {"name": "evening", "start": "16:00", "end": "21:00", "max": 1},
                    ],
                },
                "explanation": "Обнаружен недельный лимит по одному направлению с двумя временными окнами.",
                "confidence": 0.98,
            },
        },
        {
            "text": "По понедельникам и средам допускаются две спокойные тренировки подряд",
            "json": {
                "rule_type": "calm_consecutive",
                "severity": "hard",
                "name": "Спокойные подряд в выбранные дни",
                "params_json": {"weekdays": [0, 2], "max_consecutive": 2, "category": "calm"},
                "explanation": "Есть явные дни недели и ограничение на количество подряд.",
                "confidence": 0.97,
            },
        },
        {
            "text": "Силовые и кардио тренировки должны чередоваться в остальные дни",
            "json": {
                "rule_type": "alternation",
                "severity": "hard",
                "name": "Чередование силовых и кардио",
                "params_json": {
                    "weekdays": [1, 3, 4, 5, 6],
                    "categories": ["strength", "cardio"],
                    "mode": "strict_alternate",
                },
                "explanation": "Найден паттерн чередования двух категорий.",
                "confidence": 0.96,
            },
        },
        {
            "text": "Две одинаковые тренировки в один день утром или вечером ставить нельзя",
            "json": {
                "rule_type": "daily_duplicate_limit",
                "severity": "hard",
                "name": "Запрет дублей в день (утро/вечер)",
                "params_json": {
                    "scope": "bucket",
                    "max_per_bucket_per_day": 1,
                    "buckets": [
                        {"name": "morning", "start": "09:00", "end": "14:00"},
                        {"name": "evening", "start": "16:00", "end": "21:00"}
                    ]
                },
                "explanation": "Найден запрет повторять одинаковый тип занятия в одном окне дня.",
                "confidence": 0.95
            },
        },
    ]
    return (
        "Ты преобразуешь правило распределения расписания в JSON.\n"
        "Верни ТОЛЬКО JSON, без markdown и пояснений вне JSON.\n"
        "Если не можешь уверенно распознать — верни JSON: "
        '{"need_clarification": true, "error": "...", "explanation":"...","confidence":0.0}\n'
        f"Схема ответа: {json.dumps(schema, ensure_ascii=False)}\n"
        f"Примеры: {json.dumps(examples, ensure_ascii=False)}\n"
        f"Правило: {rule_text}"
    )


def _validate_ai_result(payload: Dict[str, Any]) -> Tuple[bool, str]:
    if payload.get("need_clarification") is True:
        return False, payload.get("error") or "Нужно уточнение правила."

    rule_type = payload.get("rule_type")
    severity = payload.get("severity")
    params = payload.get("params_json")

    if rule_type not in {"weekly_limit", "calm_consecutive", "alternation", "daily_duplicate_limit"}:
        return False, "AI вернул неподдерживаемый тип правила."
    if severity not in {"hard", "soft"}:
        return False, "AI вернул неподдерживаемую жесткость."
    if not isinstance(params, dict):
        return False, "AI вернул некорректные параметры правила."

    if rule_type == "weekly_limit":
        if not params.get("workout_name"):
            return False, "Для weekly_limit не задан workout_name."
        buckets = params.get("buckets")
        if not isinstance(buckets, list) or not buckets:
            return False, "Для weekly_limit не заданы buckets."
    elif rule_type == "calm_consecutive":
        if not isinstance(params.get("weekdays"), list):
            return False, "Для calm_consecutive не заданы weekdays."
        if not isinstance(params.get("max_consecutive"), int):
            return False, "Для calm_consecutive не задан max_consecutive."
    elif rule_type == "alternation":
        if not isinstance(params.get("weekdays"), list):
            return False, "Для alternation не заданы weekdays."
        if not isinstance(params.get("categories"), list) or len(params.get("categories")) < 2:
            return False, "Для alternation не заданы categories."
    elif rule_type == "daily_duplicate_limit":
        if not isinstance(params.get("buckets"), list) or not params.get("buckets"):
            return False, "Для daily_duplicate_limit не заданы buckets."
        if not isinstance(params.get("max_per_bucket_per_day"), int):
            return False, "Для daily_duplicate_limit не задан max_per_bucket_per_day."

    return True, ""


def try_parse_rule_with_ai(rule_text: str):
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
