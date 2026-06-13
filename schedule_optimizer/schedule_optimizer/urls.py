"""Главная карта маршрутов проекта: подключает приложение core, админку и обработчики ошибок."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core import error_handlers
from core import views as core_views


urlpatterns = [
    path('', include('core.urls')),

    # Страница управления пользователями проекта.
    path('admin/users/', core_views.user_management, name='user_management'),

    # Стандартная админ-панель Django.
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = error_handlers.handler400
handler403 = error_handlers.handler403
handler404 = error_handlers.handler404
handler500 = error_handlers.handler500
