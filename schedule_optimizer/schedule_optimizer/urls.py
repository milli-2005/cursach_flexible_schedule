from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core import views as core_views
from core import api_views

urlpatterns = [
    path('', include('core.urls')),

    # Управление пользователями (только для администраторов) здесь, потому что кастмная админка, а пути с admin на другое везде не хочется переименовывать
    # API для управления пользователями - ДО admin.site.urls
    path('api/users/', api_views.api_get_users, name='api_get_users'),
    path('api/invite-user/', api_views.api_invite_user, name='api_invite_user'),
    path('api/users/<int:user_id>/', api_views.api_get_user_detail, name='api_get_user_detail'),
    path('api/users/<int:user_id>/update/', api_views.api_update_user, name='api_update_user'),
    path('api/users/<int:user_id>/delete/', api_views.api_delete_user, name='api_delete_user'),
    path('api/users/<int:user_id>/reset-password/', api_views.api_reset_user_password, name='api_reset_user_password'),

    # Управление пользователями (только для администраторов) - теперь через API
    # Этот путь для отображения страницы управления
    path('admin/users/', core_views.user_management, name='user_management'),

    #сначала в главном файле путей админку видит джанговскую, а  сделала так чтобы мою видел
    path('admin/', admin.site.urls),
]

# Для обслуживания медиафайлов в режиме разработки
if settings.DEBUG:
    # "Сервер Django, начни отдавать файлы из MEDIA_ROOT по адресу MEDIA_URL!"
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

