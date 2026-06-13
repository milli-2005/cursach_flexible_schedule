"""Публичные страницы и простые страницы без сложной бизнес-логики."""

from .auth import *

def index(request):
    """Главная страница сайта."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('about')


def about(request):
    """Страница "О системе"."""
    return render(request, 'core/about.html')


@login_required
def chat_page(request):
    """Встроенный чат между пользователями."""
    return render(request, 'core/chat/chat.html')
