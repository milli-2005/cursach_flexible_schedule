"""
Админ-панель для управления моделями.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import *

# Регистрируем модели в админке
admin.site.register(UserProfile)
admin.site.register(Employee)
admin.site.register(Shift)
admin.site.register(Schedule)
admin.site.register(ShiftAssignment)
admin.site.register(TimeOffRequest)
admin.site.register(ShiftSwapRequest)
admin.site.register(OptimizationRule)

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