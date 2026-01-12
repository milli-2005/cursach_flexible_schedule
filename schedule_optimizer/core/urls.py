"""
URL-адреса приложения core.
Здесь определяем маршруты для страниц приложения.
"""
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Основные страницы
    path('', views.index, name='index'),
    path('about/', views.about, name='about'),

    # Аутентификация
    path('login/', views.custom_login, name='login'),
    path('logout/', views.custom_logout, name='logout'),

    # Личный кабинет и профиль
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('switch-role/', views.switch_role, name='switch_role'),

    # Графики и планирование
    path('schedules/', views.schedule_view, name='schedule_view'),
    path('optimization/', views.optimization_view, name='optimization'),

    # Для сотрудников
    path('my-schedule/', views.employee_schedule, name='employee_schedule'),
    path('timeoff/', views.timeoff_requests, name='timeoff_requests'),
    path('shift-swaps/', views.shift_swaps, name='shift_swaps'),

    # Отчеты
    path('reports/', views.reports, name='reports'),
]