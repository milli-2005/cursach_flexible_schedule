# core/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import api_views
from . import api_workout_views
from . import api_schedule_views

urlpatterns = [
    # Основные страницы
    path('', views.index, name='index'),
    path('about/', views.about, name='about'),

    # Аутентификация
    path('login/', views.custom_login, name='login'),
    path('logout/', views.custom_logout, name='logout'),

    # Личный кабинет и профиль
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile_view, name='profile_view'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/change-password/', views.change_password, name='change_password'),

    # Для сотрудников
    path('my-schedule/', views.employee_schedule, name='employee_schedule'),
    path('timeoff/', views.timeoff_requests, name='timeoff_requests'),
    path('shift-swaps/', views.shift_swaps, name='shift_swaps'),

path('my-availability/', views.my_availability, name='my_availability'),

    # Отчеты
    path('reports/', views.reports, name='reports'),

    # API для управления пользователями
    path('api/users/', api_views.api_get_users, name='api_get_users'),
    path('api/invite-user/', api_views.api_invite_user, name='api_invite_user'),
    path('api/users/<int:user_id>/', api_views.api_get_user_detail, name='api_get_user_detail'),
    path('api/users/<int:user_id>/update/', api_views.api_update_user, name='api_update_user'),
    path('api/users/<int:user_id>/delete/', api_views.api_delete_user, name='api_delete_user'),
    path('api/users/<int:user_id>/reset-password/', api_views.api_reset_user_password, name='api_reset_user_password'),

    # API для управления типами занятий
    path('workout-types/', views.workout_types, name='workout_types'),
    path('api/workout-types/', api_workout_views.api_get_workout_types, name='api_get_workout_types'),
    path('api/workout-types/create/', api_workout_views.api_create_workout_type, name='api_create_workout_type'),
    path('api/workout-types/<int:workout_type_id>/update/', api_workout_views.api_update_workout_type, name='api_update_workout_type'),
    path('api/workout-types/<int:workout_type_id>/delete/', api_workout_views.api_delete_workout_type, name='api_delete_workout_type'),


    # Графики и планирование
    path('schedules/', views.schedule_view, name='schedule_view'),
    path('schedules/create/', views.create_schedule_view, name='create_schedule'),
    path('api/schedule/save/', api_schedule_views.api_save_schedule, name='api_save_schedule'),
    path('schedules/<int:schedule_id>/', views.schedule_detail, name='schedule_detail'),
    path('schedules/<int:schedule_id>/edit/', views.edit_schedule_view, name='edit_schedule'),
    path('api/schedule/<int:schedule_id>/update/', api_schedule_views.api_update_schedule, name='api_update_schedule'),
    path('schedules/<int:schedule_id>/delete/', views.delete_schedule_view, name='delete_schedule'),

    #страницу согласования
    path('schedules/<int:schedule_id>/approve/', views.approve_schedule_view, name='approve_schedule'),


    path('optimization/', views.optimization_view, name='optimization'),
]
