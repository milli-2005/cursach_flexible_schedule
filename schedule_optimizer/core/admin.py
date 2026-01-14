# core/admin.py
"""
Админ-панель для управления моделями.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import *

# Регистрируем модели в админке
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'department', 'position')
    list_filter = ('role', 'department')
    search_fields = ('user__username', 'user__email', 'department', 'position')

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'max_hours_per_week', 'min_hours_per_week', 'hourly_rate')
    list_filter = ('max_hours_per_week', 'min_hours_per_week')

@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ('name', 'shift_type', 'start_time', 'end_time', 'required_employees')
    list_filter = ('shift_type',)

@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'status', 'created_by', 'created_at')
    list_filter = ('status', 'created_by', 'created_at')

@admin.register(ShiftAssignment)
class ShiftAssignmentAdmin(admin.ModelAdmin):
    list_display = ('schedule', 'employee', 'shift', 'date', 'status')
    list_filter = ('status', 'date', 'shift__shift_type')

@admin.register(TimeOffRequest)
class TimeOffRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'request_type', 'start_date', 'end_date', 'status')
    list_filter = ('status', 'request_type', 'start_date')

@admin.register(ShiftSwapRequest)
class ShiftSwapRequestAdmin(admin.ModelAdmin):
    list_display = ('from_employee', 'to_employee', 'shift_assignment', 'status', 'created_at')
    list_filter = ('status', 'created_at')

@admin.register(OptimizationRule)
class OptimizationRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'rule_type', 'priority', 'is_active')
    list_filter = ('rule_type', 'is_active', 'priority')


# Расширяем стандартную админку User
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Профиль'

class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]

# Перерегистрируем UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
