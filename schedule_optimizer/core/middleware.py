"""Middleware-проверки, которые выполняются вокруг каждого HTTP-запроса."""

import json

from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse

from .error_utils import humanize_error_text, humanize_exception


class FriendlyErrorMiddleware:
    """Перехватывает ошибки ответа и показывает пользователю более дружелюбную страницу."""
    def __init__(self, get_response):
        """Выполняет вспомогательное действие внутри своей части проекта."""
        self.get_response = get_response

    def __call__(self, request):
        """Выполняет вспомогательное действие внутри своей части проекта."""
        try:
            response = self.get_response(request)
            return self._normalize_json_error_response(request, response)
        except Exception as exc:
            message = humanize_exception(exc)
            wants_json = request.path.startswith("/api/") or "application/json" in request.headers.get("Accept", "")

            if wants_json:
                return JsonResponse(
                    {"success": False, "error": message},
                    status=500,
                )

            return render(
                request,
                "core/errors/500.html",
                {"error_message": message},
                status=500,
            )

    def _normalize_json_error_response(self, request, response):
        """Приводит значение к единому формату, чтобы сравнения и фильтры работали стабильно."""
        if not request.path.startswith("/api/"):
            return response

        content_type = response.headers.get("Content-Type", "")
        if response.status_code < 400 or "application/json" not in content_type:
            return response

        try:
            payload = json.loads(response.content.decode("utf-8"))
        except Exception:
            return response

        if isinstance(payload, dict):
            if isinstance(payload.get("error"), str):
                payload["error"] = humanize_error_text(payload["error"])
            if isinstance(payload.get("message"), str):
                payload["message"] = humanize_error_text(payload["message"])

            errors_obj = payload.get("errors")
            if isinstance(errors_obj, dict):
                normalized = {}
                for key, value in errors_obj.items():
                    if isinstance(value, list):
                        normalized[key] = [
                            humanize_error_text(item) if isinstance(item, str) else item
                            for item in value
                        ]
                    else:
                        normalized[key] = value
                payload["errors"] = normalized

            return JsonResponse(payload, status=response.status_code)

        return response


class ForcePasswordChangeMiddleware:
    """
    Если у пользователя установлен временный пароль (invitation_timestamp),
    принудительно ведем его на страницу смены пароля до завершения смены.
    """

    def __init__(self, get_response):
        """Выполняет вспомогательное действие внутри своей части проекта."""
        self.get_response = get_response

    def __call__(self, request):
        """Выполняет вспомогательное действие внутри своей части проекта."""
        user = getattr(request, "user", None)
        if user and user.is_authenticated and hasattr(user, "profile"):
            profile = user.profile
            must_change_password = bool(profile.invitation_timestamp)

            if must_change_password:
                allowed_paths = {
                    reverse("change_password"),
                    reverse("logout"),
                }
                current_path = request.path
                is_allowed = any(current_path.startswith(path) for path in allowed_paths)
                is_static = current_path.startswith("/static/") or current_path.startswith("/media/")

                if not is_allowed and not is_static:
                    return redirect("change_password")

        return self.get_response(request)
