from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core import views as core_views
from core import api_views

urlpatterns = [
    path('', include('core.urls')),

    # Этот путь для отображения страницы управления
    path('admin/users/', core_views.user_management, name='user_management'),

    #сначала в главном файле путей админку видит джанговскую, а  сделала так чтобы мою видел
    path('admin/', admin.site.urls),
]

# Для обслуживания медиафайлов в режиме разработки
if settings.DEBUG:
    # "Сервер Django, начни отдавать файлы из MEDIA_ROOT по адресу MEDIA_URL!"
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

