# core/admin.py
"""
Админ-панель для управления моделями.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import *

# --- Обновляем регистрацию UserProfile ---
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Настраивает отображение и фильтры модели в административной панели Django."""
    list_display = ('user', 'role')
    list_filter = ['role']
    search_fields = ('user__username', 'user__email')

# --- Обновляем регистрацию ShiftAssignment ---
@admin.register(ShiftAssignment)
class ShiftAssignmentAdmin(admin.ModelAdmin):
    """Настраивает отображение и фильтры модели в административной панели Django."""
    list_display = ('schedule', 'employee', 'workout_type', 'date', 'status') # Заменили 'shift' на 'workout_type'
    list_filter = ('status', 'date', 'workout_type')
    # Если workout_type может быть NULL, лучше использовать 'workout_type__name'


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """Настраивает отображение и фильтры модели в административной панели Django."""
    list_display = (
        'user_profile',
        'is_substitute',
        'substitute_priority',
        'max_hours_per_week',
        'min_hours_per_week',
        'hourly_rate',
    )
    list_filter = ('is_substitute', 'max_hours_per_week', 'min_hours_per_week')
    filter_horizontal = ('workout_types',)

@admin.register(WorkoutType) # Новая модель
class WorkoutTypeAdmin(admin.ModelAdmin):
    """Настраивает отображение и фильтры модели в административной панели Django."""
    list_display = ('name', 'description')



@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    """Настраивает отображение и фильтры модели в административной панели Django."""
    list_display = ('name', 'start_date', 'end_date', 'status', 'created_by', 'created_at')
    list_filter = ('status', 'created_by', 'created_at')


@admin.register(ScheduleVersion)
class ScheduleVersionAdmin(admin.ModelAdmin):
    """Настраивает отображение и фильтры модели в административной панели Django."""
    list_display = ('schedule', 'version_number', 'schedule_name', 'change_source', 'created_by', 'created_at')
    list_filter = ('change_source', 'created_at')
    search_fields = ('schedule__name', 'schedule_name', 'change_note')
    ordering = ('-created_at',)


@admin.register(ScheduleVersionAssignment)
class ScheduleVersionAssignmentAdmin(admin.ModelAdmin):
    """Настраивает отображение и фильтры модели в административной панели Django."""
    list_display = ('schedule_version', 'date', 'start_time', 'employee', 'workout_type')
    list_filter = ('date', 'workout_type')
    search_fields = ('schedule_version__schedule__name', 'employee__user__username')

@admin.register(TimeOffRequest)
class TimeOffRequestAdmin(admin.ModelAdmin):
    """Настраивает отображение и фильтры модели в административной панели Django."""
    list_display = ('employee', 'request_type', 'start_date', 'end_date', 'status')
    list_filter = ('status', 'request_type', 'start_date')

# core/admin.py

from django.contrib import admin
from .models import ShiftSwapRequest, SwapShift

class SwapShiftInline(admin.TabularInline):
    """Класс группирует данные и поведение для своей части проекта."""
    model = SwapShift
    extra = 0
    readonly_fields = ('shift_assignment',)
    can_delete = False

@admin.register(ShiftSwapRequest)
class ShiftSwapRequestAdmin(admin.ModelAdmin):
    """Настраивает отображение и фильтры модели в административной панели Django."""
    list_display = ('from_employee', 'to_employee', 'get_shifts', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    inlines = [SwapShiftInline]

    def get_shifts(self, obj):
        """Выполняет вспомогательное действие внутри своей части проекта."""
        return ", ".join([
            f"{s.shift_assignment.date} {s.shift_assignment.start_time}"
            for s in obj.shifts.all()
        ])
    get_shifts.short_description = "Смены"

@admin.register(OptimizationRule)
class OptimizationRuleAdmin(admin.ModelAdmin):
    """Настраивает отображение и фильтры модели в административной панели Django."""
    list_display = ('name', 'rule_type', 'priority', 'is_active')
    list_filter = ('rule_type', 'is_active', 'priority')


# --- Расширяем стандартную админку User ---
class UserProfileInline(admin.StackedInline):
    """Класс группирует данные и поведение для своей части проекта."""
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Профиль'

class UserAdmin(BaseUserAdmin):
    """Настраивает отображение и фильтры модели в административной панели Django."""
    inlines = [UserProfileInline]

# Перерегистрируем UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# core/admin.py
from django.contrib import admin
from .models import Availability

@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    """Настраивает отображение и фильтры модели в административной панели Django."""
    list_display = ['employee', 'date', 'start_time', 'end_time', 'updated_at']
    list_filter = ['employee', 'date']


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    """Настраивает отображение и фильтры модели в административной панели Django."""
    list_display = ('id', 'is_group', 'title', 'participant_a', 'participant_b', 'updated_at')
    search_fields = ('title', 'participant_a__username', 'participant_b__username', 'participants__username')
    list_filter = ('is_group', 'updated_at')
    filter_horizontal = ('participants',)
    ordering = ('-updated_at',)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    """Настраивает отображение и фильтры модели в административной панели Django."""
    list_display = ('id', 'conversation', 'sender', 'is_read', 'created_at')
    search_fields = ('sender__username', 'text')
    list_filter = ('is_read', 'created_at')
    ordering = ('-created_at',)


@admin.register(ChatMessageRead)
class ChatMessageReadAdmin(admin.ModelAdmin):
    """Настраивает отображение и фильтры модели в административной панели Django."""
    list_display = ('id', 'message', 'user', 'read_at')
    search_fields = ('user__username', 'message__text')
    list_filter = ('read_at',)
    ordering = ('-id',)


@admin.register(ChatConversationPin)
class ChatConversationPinAdmin(admin.ModelAdmin):
    """Настраивает отображение и фильтры модели в административной панели Django."""
    list_display = ('id', 'user', 'conversation', 'created_at')
    search_fields = ('user__username', 'conversation__title')
    list_filter = ('created_at',)
    ordering = ('-created_at',)
