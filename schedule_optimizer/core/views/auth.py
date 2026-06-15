"""Страницы авторизации, профиля, дашбордов, управления пользователями."""
import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.conf import settings
from django.http import JsonResponse
from ..email_utils import send_mail_with_fallback
from ..models import *
from ..forms import UserProfileEditForm
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
from collections import defaultdict



logger = logging.getLogger(__name__)

def is_manager(user):
    """
    Проверяет, является ли пользователь руководителем.
    """
    if not hasattr(user, 'profile'):
        return False
    return user.profile.role == 'manager'


def is_admin(user):
    """Проверяет, является ли пользователь администратором."""
    if not hasattr(user, 'profile'):
        return False
    return user.profile.role == 'manager' or user.is_superuser

# Авторизация, профиль и дашборды
def custom_login(request):
    """Кастомная страница входа в систему."""
    if request.user.is_authenticated:
        if hasattr(request.user, 'profile') and request.user.profile.invitation_timestamp:
            return redirect('change_password')
        return redirect('dashboard')

    if request.method == 'POST':
        login_data = request.POST.copy()
        login_data['username'] = login_data.get('username', '').strip()
        login_data['password'] = login_data.get('password', '').strip()
        form = AuthenticationForm(data=login_data)
        if form.is_valid():
            user = form.get_user()

            # Проверяем, не истёк ли срок действия временного пароля
            if hasattr(user, 'profile') and user.profile.is_temporary_password_expired():
                messages.error(request,
                               "Временный пароль устарел. Пожалуйста, свяжитесь с администратором для получения нового.")
                # Важно: не логиним пользователя, если пароль истёк
                return render(request, 'core/login.html', {'form': form})

            login(request, user)
            if hasattr(user, 'profile') and user.profile.invitation_timestamp:
                messages.info(request, "Для продолжения работы сначала смените временный пароль.")
                return redirect('change_password')

            messages.success(request, f"Добро пожаловать, {user.username}!")
            return redirect('dashboard')  # Перенаправляем на дашборд после входа
        else:
            messages.error(request, "Неверное имя пользователя или пароль.")
    else:
        form = AuthenticationForm()

    return render(request, 'core/login.html', {'form': form})


@login_required
def custom_logout(request):
    """Выход из системы."""
    logout(request)
    return redirect('index')


@login_required
def dashboard(request):
    """Личный кабинет пользователя."""
    user = request.user
    profile = user.profile
    context = {
        'user': user,
        'profile': profile,
    }

    # В зависимости от роли показываем разную информацию и перенаправляем или рендерим
    if profile.role == 'employee':
        # Для сотрудника показываем его смены и заявки
        try:
            employee_model = Employee.objects.get(user_profile=profile)
            context['employee'] = employee_model
            # Здесь можно добавить логику для получения смен сотрудника
        except Employee.DoesNotExist:
            pass
        return render(request, 'core/dashboard/dashboard_employee.html', context)
    elif profile.role == 'manager':
        # Для менеджера
        schedules = Schedule.objects.all()[:5]  # Пример
        context['schedules'] = schedules
        return render(request, 'core/dashboard/dashboard_manager.html', context)
    else:
        # На всякий случай, если роль неизвестна
        messages.error(request, "Неизвестная роль пользователя.")
        return redirect('dashboard')




@login_required
def profile_view(request):
    """Показывает профиль текущего пользователя вместе с параметрами сотрудника."""
    user = request.user
    profile = user.profile
    employee, created = Employee.objects.get_or_create(user_profile=profile)

    context = {
        'user': user,
        'profile': profile,
        'employee': employee,
    }
    return render(request, 'core/profile/profile.html', context)



@login_required
def profile_edit(request):
    """Обрабатывает форму редактирования телефона, отчества и аватара пользователя."""
    user = request.user
    profile = user.profile

    if request.method == 'POST':
        form = UserProfileEditForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль успешно обновлён.")
            return redirect('profile_view')
    else:
        form = UserProfileEditForm(instance=profile)

    context = {'form': form}
    return render(request, 'core/profile/edit.html', context)



def change_password(request):
    """
    Смена пароля после регистрации по приглашению.
    Предполагается, что пользователь уже вошёл в систему с временным паролем.
    """
    from django.contrib.auth.forms import SetPasswordForm
    from django.contrib.auth import update_session_auth_hash  # Для обновления сессии

    user = request.user
    if not user.is_authenticated:
        messages.error(request, "Пожалуйста, войдите в систему, используя временный пароль из письма.")
        return redirect('login')

    # Проверяем, не истёк ли срок действия временного пароля при доступе к странице смены пароля
    if hasattr(user, 'profile') and user.profile.is_temporary_password_expired():
        messages.error(request, "Срок действия временного пароля истёк. Пожалуйста, свяжитесь с администратором для получения нового.")
        return redirect('login')  # Или на главную, если не хочет логиниться снова

    if request.method == 'POST':
        form = SetPasswordForm(user, request.POST)  # Передаём текущего пользователя
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Важно: обновляем сессию, чтобы пользователь не вышел

            # Clear temporary timestamp after password change
            if hasattr(user, 'profile'):
                user.profile.invitation_timestamp = None
                user.profile.save()

            messages.success(request, "Ваш пароль был успешно изменён.")
            return redirect('profile_view')  # Перенаправляем на профиль после смены пароля
    else:
        form = SetPasswordForm(user)  # Передаём текущего пользователя

    context = {
        'form': form,
    }
    return render(request, 'core/profile/change_password.html', context)

@login_required
@user_passes_test(is_admin)
def user_management(request):
    """Открывает страницу управления пользователями для руководителя или администратора."""
    context = {}
    return render(request, 'core/dashboard/user_management.html', context)
