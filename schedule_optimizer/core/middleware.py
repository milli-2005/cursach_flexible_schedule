import json

from django.http import JsonResponse
from django.shortcuts import render

from .error_utils import humanize_error_text, humanize_exception


class FriendlyErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
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
