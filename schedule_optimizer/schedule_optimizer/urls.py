from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
]

# Для обслуживания медиафайлов в режиме разработки
if settings.DEBUG:
    # "Сервер Django, начни отдавать файлы из MEDIA_ROOT по адресу MEDIA_URL!"
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

