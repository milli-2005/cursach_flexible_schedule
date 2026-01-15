from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core import views

urlpatterns = [
    path('', include('core.urls')),

    # Управление пользователями (только для администраторов) здесь, потому что кастмная админка, а пути с admin на другое везде не хочется переименовывать
    path('admin/users/', views.user_management, name='user_management'),
    path('admin/users/invite/', views.invite_user, name='invite_user'),
    path('admin/users/reset-password/<int:user_id>/', views.reset_user_password, name='reset_user_password'),

    #сначала в главном файле путей админку видит джанговскую, а  сделала так чтобы мою видел
    path('admin/', admin.site.urls),
]

# Для обслуживания медиафайлов в режиме разработки
if settings.DEBUG:
    # "Сервер Django, начни отдавать файлы из MEDIA_ROOT по адресу MEDIA_URL!"
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

