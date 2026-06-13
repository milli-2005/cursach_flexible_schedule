"""Обработчики страниц ошибок HTTP 400, 403, 404 и 500."""

from django.shortcuts import render


def handler400(request, exception=None):
    """Показывает страницу ошибки 400, когда запрос пользователя некорректен."""
    return render(
        request,
        "core/errors/400.html",
        {"error_message": "Запрос содержит ошибку. Проверьте введенные данные и попробуйте снова."},
        status=400,
    )


def handler403(request, exception=None):
    """Показывает страницу ошибки 403, когда доступ к действию запрещен."""
    return render(
        request,
        "core/errors/403.html",
        {"error_message": "У вас недостаточно прав для доступа к этой странице."},
        status=403,
    )


def handler404(request, exception=None):
    """Показывает страницу ошибки 404, когда нужная страница или объект не найдены."""
    return render(
        request,
        "core/errors/404.html",
        {"error_message": "Страница не найдена. Возможно, ссылка устарела или введена с ошибкой."},
        status=404,
    )


def handler500(request):
    """Показывает страницу ошибки 500 при непредвиденной ошибке сервера."""
    return render(
        request,
        "core/errors/500.html",
        {"error_message": "На сервере произошла ошибка. Попробуйте обновить страницу чуть позже."},
        status=500,
    )
