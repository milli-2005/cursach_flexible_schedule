"""Маршруты приложения core, сгруппированные по разделам интерфейса и API."""

from django.urls import path

from . import views
from .api import schedule_views
from .api.chat_views import (
    api_chat_conversations,
    api_chat_create_group,
    api_chat_delete_group,
    api_chat_leave_group,
    api_chat_messages,
    api_chat_send_message,
    api_chat_start_conversation,
    api_chat_toggle_pin,
    api_chat_unread_count,
    api_chat_update_group,
    api_chat_users,
)
from .api.swap_views import (
    api_approve_swap_request,
    api_create_swap_request,
    api_employees_for_swap,
    api_my_shifts_for_swap,
    api_reject_swap_request,
    api_swap_request_candidates,
)
from .api.user_views import (
    api_delete_user,
    api_get_user_detail,
    api_get_users,
    api_invite_user,
    api_reset_user_password,
    api_update_user,
)
from .api.workout_views import (
    api_create_workout_type,
    api_delete_workout_type,
    api_get_employee_workout_types,
    api_get_workout_types,
    api_update_workout_type,
)


urlpatterns = [
    # Основные страницы
    path('', views.index, name='index'),
    path('about/', views.about, name='about'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('chat/', views.chat_page, name='chat_page'),

    # Авторизация и профиль
    path('login/', views.custom_login, name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('profile/', views.profile_view, name='profile_view'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/change-password/', views.change_password, name='change_password'),

    # Пользователи
    path('api/users/', api_get_users, name='api_get_users'),
    path('api/users/<int:user_id>/', api_get_user_detail, name='api_get_user_detail'),
    path('api/invite-user/', api_invite_user, name='api_invite_user'),
    path('api/users/<int:user_id>/update/', api_update_user, name='api_update_user'),
    path('api/users/<int:user_id>/delete/', api_delete_user, name='api_delete_user'),
    path('api/users/<int:user_id>/reset-password/', api_reset_user_password, name='api_reset_user_password'),

    # Расписания и планирование
    path('schedules/', views.schedule_view, name='schedule_view'),
    path('schedules/create/', views.create_schedule_view, name='create_schedule'),
    path('schedules/rules/', views.distribution_rules_page, name='distribution_rules'),
    path('schedules/<int:schedule_id>/', views.schedule_detail, name='schedule_detail'),
    path('schedules/<int:schedule_id>/export/pdf/', views.schedule_pdf_export, name='schedule_pdf_export'),
    path('schedules/<int:schedule_id>/edit/', views.edit_schedule_view, name='edit_schedule'),
    path('schedules/<int:schedule_id>/delete/', views.delete_schedule_view, name='delete_schedule'),
    path('my-schedule/', views.employee_schedule, name='employee_schedule'),
    path('my-availability/', views.my_availability, name='my_availability'),
    path('remind/availability/', views.send_availability_reminder_manual, name='send_availability_reminder'),

    # API расписаний
    path('api/schedule/save/', schedule_views.api_save_schedule, name='api_save_schedule'),
    path('api/schedule/substitute-candidates/', schedule_views.api_substitute_candidates, name='api_substitute_candidates'),
    path('api/schedule/<int:schedule_id>/update/', schedule_views.api_update_schedule, name='api_update_schedule'),
    path('api/schedule/<int:schedule_id>/versions/', schedule_views.api_schedule_versions, name='api_schedule_versions'),
    path('api/schedule/<int:schedule_id>/versions/compare/', schedule_views.api_compare_schedule_versions, name='api_compare_schedule_versions'),
    path('api/schedule/<int:schedule_id>/versions/<int:version_id>/restore/', schedule_views.api_restore_schedule_version, name='api_restore_schedule_version'),
    path('api/schedule/<int:schedule_id>/approve/', schedule_views.api_approve_schedule, name='api_approve_schedule'),
    path('api/schedule/<int:schedule_id>/simulate-variants/', schedule_views.api_simulate_schedule_variants, name='api_simulate_schedule_variants'),
    path('api/schedule/<int:schedule_id>/status/', schedule_views.api_set_schedule_status, name='api_set_schedule_status'),

    # Правила распределения занятий
    path('api/distribution-rules/parse/', views.api_parse_distribution_rule, name='api_parse_distribution_rule'),
    path('api/distribution-rules/save/', views.api_save_distribution_rule, name='api_save_distribution_rule'),
    path('api/distribution-rules/<int:rule_id>/update/', views.api_update_distribution_rule, name='api_update_distribution_rule'),
    path('api/distribution-rules/<int:rule_id>/toggle/', views.api_toggle_distribution_rule, name='api_toggle_distribution_rule'),
    path('api/distribution-rules/<int:rule_id>/delete/', views.api_delete_distribution_rule, name='api_delete_distribution_rule'),
    path('api/distribution-rules/test/', views.api_test_distribution_rules, name='api_test_distribution_rules'),

    # Занятия и направления
    path('workout-types/', views.workout_types, name='workout_types'),
    path('api/workout-types/', api_get_workout_types, name='api_get_workout_types'),
    path('api/workout-types/create/', api_create_workout_type, name='api_create_workout_type'),
    path('api/workout-types/<int:workout_type_id>/update/', api_update_workout_type, name='api_update_workout_type'),
    path('api/workout-types/<int:workout_type_id>/delete/', api_delete_workout_type, name='api_delete_workout_type'),
    path('api/employee-workout-types/<int:user_id>/', api_get_employee_workout_types, name='api_get_employee_workout_types'),

    # Обмен сменами
    path('shift-swaps/', views.shift_swaps, name='shift_swaps'),
    path('manager-swaps/', views.manager_swap_requests, name='manager_swap_requests'),
    path('api/my-shifts-for-swap/', api_my_shifts_for_swap, name='api_my_shifts_for_swap'),
    path('api/employees-for-swap/', api_employees_for_swap, name='api_employees_for_swap'),
    path('api/create-swap-request/', api_create_swap_request, name='api_create_swap_request'),
    path('api/swap-request/<int:swap_id>/approve/', api_approve_swap_request, name='api_approve_swap_request'),
    path('api/swap-request/<int:swap_id>/reject/', api_reject_swap_request, name='api_reject_swap_request'),
    path('api/swap-request/<int:swap_id>/candidates/', api_swap_request_candidates, name='api_swap_request_candidates'),

    # Чат
    path('api/chat/users/', api_chat_users, name='api_chat_users'),
    path('api/chat/conversations/', api_chat_conversations, name='api_chat_conversations'),
    path('api/chat/conversations/start/', api_chat_start_conversation, name='api_chat_start_conversation'),
    path('api/chat/conversations/group/', api_chat_create_group, name='api_chat_create_group'),
    path('api/chat/conversations/group/update/', api_chat_update_group, name='api_chat_update_group'),
    path('api/chat/conversations/group/delete/', api_chat_delete_group, name='api_chat_delete_group'),
    path('api/chat/conversations/group/leave/', api_chat_leave_group, name='api_chat_leave_group'),
    path('api/chat/conversations/pin/', api_chat_toggle_pin, name='api_chat_toggle_pin'),
    path('api/chat/conversations/<int:conversation_id>/messages/', api_chat_messages, name='api_chat_messages'),
    path('api/chat/messages/send/', api_chat_send_message, name='api_chat_send_message'),
    path('api/chat/unread-count/', api_chat_unread_count, name='api_chat_unread_count'),

    # Отчеты
    path('reports/', views.reports_view, name='reports'),
    path('reports/export/tabel/', views.export_operational_excel, name='export_operational_excel'),
]
