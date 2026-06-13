"""Утилиты для преобразования технических ошибок в понятные сообщения для пользователя и API."""

import json
import logging
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.http import JsonResponse


logger = logging.getLogger(__name__)


def humanize_error_text(text: str) -> str:
    """Заменяет технический текст ошибки на более понятное русское описание."""
    if not text:
        return "Произошла ошибка. Попробуйте снова."

    low = text.lower()
    if "list index out of range" in low:
        return "Некорректный формат времени в одном из слотов. Проверьте данные и попробуйте снова."
    if "user not found" in low:
        return "Пользователь не найден."
    if "expecting value" in low or "jsondecodeerror" in low:
        return "Не удалось прочитать данные запроса. Обновите страницу и попробуйте снова."
    if "permission denied" in low:
        return "Недостаточно прав для выполнения действия."
    return text


def humanize_exception(exc: Exception) -> str:
    """Преобразует исключение Python в сообщение, которое можно показать пользователю."""
    if isinstance(exc, json.JSONDecodeError):
        return "Не удалось прочитать данные запроса. Обновите страницу и попробуйте снова."
    if isinstance(exc, KeyError):
        field = str(exc).strip("'\"")
        return f"Не передано обязательное поле: {field}."
    if isinstance(exc, IndexError):
        return "Получены неполные данные. Проверьте формат времени и заполнение полей."
    if isinstance(exc, PermissionDenied):
        return "У вас недостаточно прав для выполнения этого действия."
    if isinstance(exc, ValidationError):
        return "Некоторые данные заполнены неверно. Проверьте форму и попробуйте снова."
    if isinstance(exc, IntegrityError):
        return "Не удалось сохранить данные из-за конфликта в базе. Проверьте уникальность значений."
    if isinstance(exc, ValueError):
        text = str(exc).strip()
        if text:
            return text
        return "Переданы некорректные данные."
    return humanize_error_text("Произошла внутренняя ошибка. Попробуйте снова или обратитесь к администратору.")


def api_error_response(
    exc: Exception,
    *,
    status: int = 400,
    success: bool = False,
    error_key: str = "error",
    extra: dict[str, Any] | None = None,
) -> JsonResponse:
    """Формирует единый JSON-ответ об ошибке для API-обработчиков."""
    message = humanize_exception(exc)
    logger.exception("API error: %s", exc)

    payload: dict[str, Any] = {"success": success, error_key: message}
    if extra:
        payload.update(extra)
    return JsonResponse(payload, status=status)
