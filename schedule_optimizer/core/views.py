# core/views.py
import secrets
import string
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import *
from .forms import UserInvitationForm, UserProfileForm, CustomSetPasswordForm # Импортируем новые формы
import logging

from .models import (
    UserProfile, Employee, Shift, Schedule, ShiftAssignment,
    TimeOffRequest, ShiftSwapRequest, OptimizationRule
)
from .forms import UserInvitationForm, UserProfileForm # Убедитесь, что импортировали UserProfileForm, если будете использовать
from .utils import generate_random_password, send_user_invitation # Импортируем наши утилиты

logger = logging.getLogger(__name__) # Инициализируем логгер


def is_admin(user):
    """Проверяет, является ли пользователь администратором."""
    if not hasattr(user, 'profile'):
        return False
    # Проверяем как роль в профиле, так и is_superuser
    return user.profile.role == 'admin' or user.is_superuser


@login_required
@user_passes_test(is_admin)
def invite_user(request):
    """
    Страница для приглашения нового пользователя.
    Доступна только администраторам.
    """
    if request.method == 'POST':
        form = UserInvitationForm(request.POST)
        if form.is_valid():
            try:
                # Генерируем случайный пароль
                raw_password = generate_random_password()
                # Создаем пользователя
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    password=raw_password, # Устанавливаем сгенерированный пароль
                    first_name=form.cleaned_data.get('first_name', ''),
                    last_name=form.cleaned_data.get('last_name', ''),
                )
                # Профиль создаётся автоматически сигналом в apps.py,
                # но мы должны обновить его атрибуты после создания
                profile = user.profile # Получаем связанный профиль
                profile.role = form.cleaned_data['role']
                profile.department = form.cleaned_data.get('department', '')
                profile.position = form.cleaned_data.get('position', '')
                profile.phone = form.cleaned_data.get('phone', '')
                # current_role автоматически установится в save() в модели
                # если не установлен явно, то на основе role
                profile.save()

                # Отправляем приглашение на email
                try:
                    send_user_invitation(user, raw_password)
                    messages.success(
                        request,
                        f'Пользователь {user.username} успешно создан. '
                        f'Приглашение отправлено на {user.email}.'
                    )
                    logger.info(f'Администратор {request.user.username} создал пользователя {user.username}')
                except Exception as e:
                    # Если email не отправился, всё равно создаём пользователя
                    # и показываем пароль администратору
                    messages.warning(
                        request,
                        f'Пользователь {user.username} создан, но email не отправлен. '
                        f'Ошибка: {str(e)}. Пароль пользователя: {raw_password}'
                    )
                    logger.error(f'Ошибка отправки email для пользователя {user.username}: {str(e)}')

                return redirect('user_management') # Перенаправляем после успешного создания
            except Exception as e:
                messages.error(request, f'Ошибка при создании пользователя: {str(e)}')
                logger.error(f'Ошибка создания пользователя: {str(e)}')
    else:
        form = UserInvitationForm()

    return render(request, 'core/invite_user.html', {'form': form})


@login_required
@user_passes_test(is_admin)
def user_management(request):
    """Страница управления пользователями для администратора."""
    users = User.objects.all().select_related('profile')
    context = {
        'users': users,
    }
    return render(request, 'core/user_management.html', context)


@login_required
@user_passes_test(is_admin)
def reset_user_password(request, user_id):
    """Сброс пароля пользователя и отправка нового на email."""
    try:
        user = get_object_or_404(User, id=user_id)
        if request.method == 'POST':
            # Генерируем новый случайный пароль
            raw_password = generate_random_password()
            # Устанавливаем новый пароль
            user.set_password(raw_password)
            user.save()

            # Отправляем email с новым паролем
            try:
                send_user_invitation(user, raw_password) # Та же функция, но с новым паролем
                messages.success(
                    request,
                    f'Новый пароль для пользователя {user.username} отправлен на {user.email}.'
                )
                logger.info(f'Администратор {request.user.username} сбросил пароль для {user.username}')
            except Exception as e:
                # Если email не отправился, показываем пароль администратору
                messages.warning(
                    request,
                    f'Пароль сброшен, но email не отправлен. '
                    f'Ошибка: {str(e)}. Новый пароль: {raw_password}'
                )
            return redirect('user_management')

        context = {
            'user': user,
        }
        return render(request, 'core/reset_password_confirm.html', context)
    except User.DoesNotExist:
        messages.error(request, 'Пользователь не найден.')
        return redirect('user_management')


def index(request):
    """Главная страница сайта."""
    # Проверяем, авторизован ли пользователь
    if request.user.is_authenticated:
        # Если да, перенаправляем на дашборд
        return redirect('dashboard')
    else:
        # Если нет, показываем базовую индексную страницу
        context = {}
        return render(request, 'core/index.html', context)


def about(request):
    """Страница "О системе"."""
    return render(request, 'core/about.html')


def custom_login(request):
    """Кастомная страница входа в систему."""
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Устанавливаем текущую роль из профиля в сессию
            if hasattr(user, 'profile'):
                request.session['current_role'] = user.profile.current_role or user.profile.role
            messages.success(request, f"Добро пожаловать, {user.username}!")
            return redirect('dashboard') # Перенаправляем на дашборд после входа
        else:
            messages.error(request, "Неверное имя пользователя или пароль.")
    else:
        form = AuthenticationForm()

    return render(request, 'core/login.html', {'form': form})


@login_required
def custom_logout(request):
    """Выход из системы."""
    logout(request)
    messages.info(request, "Вы вышли из системы.")
    return redirect('index')


@login_required
def dashboard(request):
    """Личный кабинет пользователя."""
    user = request.user
    context = {
        'user': user,
    }

    # В зависимости от роли показываем разную информацию
    if hasattr(user, 'profile'):
        role = user.profile.current_role or user.profile.role
        if role == 'employee':
            # Для сотрудника показываем его смены и заявки
            try:
                employee = Employee.objects.get(user_profile=user.profile)
                context['employee'] = employee
                # Здесь можно добавить логику для получения смен сотрудника
            except Employee.DoesNotExist:
                # Если профиль сотрудника не создан, возможно, стоит создать его автоматически или вывести предупреждение
                pass
        elif role == 'manager':
            # Для менеджера показываем его команду и смены
            # TODO: Реализовать логику для менеджера
            pass
        elif role == 'planner':
            # Для планировщика показываем графики и инструменты оптимизации
            schedules = Schedule.objects.all()[:5] # Последние 5 графиков
            context['schedules'] = schedules
        elif role == 'admin':
            # Для админа показываем статистику системы
            user_count = User.objects.count()
            context['user_count'] = user_count

    return render(request, 'core/dashboard.html', context)



@login_required
def profile_view(request):
    """
    Просмотр профиля пользователя.
    """
    user = request.user
    profile = user.profile # Предполагается, что профиль всегда существует
    context = {
        'user': user,
        'profile': profile,
    }
    return render(request, 'core/profile/view.html', context)

@login_required
def profile_edit(request):
    """
    Редактирование профиля пользователя.
    """
    user = request.user
    profile = user.profile # Предполагается, что профиль всегда существует

    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль успешно обновлён.")
            return redirect('profile_view') # Перенаправляем на просмотр после сохранения
    else:
        form = UserProfileForm(instance=profile)

    context = {
        'form': form,
    }
    return render(request, 'core/profile/edit.html', context)

def change_password(request):
    """
    Смена пароля после регистрации по приглашению.
    Предполагается, что пользователь уже вошёл в систему с временным паролем.
    """
    user = request.user
    if not user.is_authenticated:
        # Если пользователь не вошёл, перенаправляем на страницу входа
        # или показываем сообщение о том, что нужно сначала войти по временному паролю
        messages.error(request, "Пожалуйста, войдите в систему, используя временный пароль из письма.")
        return redirect('login')

    if request.method == 'POST':
        form = CustomSetPasswordForm(user, request.POST) # Передаём текущего пользователя
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Важно: обновляем сессию, чтобы пользователь не вышел
            messages.success(request, "Ваш пароль был успешно изменён.")
            return redirect('profile_view') # Перенаправляем на профиль после смены пароля
    else:
        form = CustomSetPasswordForm(user) # Передаём текущего пользователя

    context = {
        'form': form,
    }
    return render(request, 'core/profile/change_password.html', context)


@login_required
def switch_role(request):
    """Смена текущей роли пользователя."""
    if request.method == 'POST':
        new_role = request.POST.get('role')
        if new_role in dict(UserProfile.ROLE_CHOICES):
            if hasattr(request.user, 'profile'):
                request.user.profile.current_role = new_role
                request.user.profile.save()
                request.session['current_role'] = new_role # Обновляем сессию
                messages.success(request, f"Роль изменена на {request.user.profile.get_current_role_display()}")
            else:
                messages.error(request, "Профиль пользователя не найден.")
            return redirect('dashboard') # Возвращаемся на дашборд

    # GET запрос - показываем форму выбора роли
    if hasattr(request.user, 'profile'):
        # В текущей реализации пользователь имеет одну основную роль,
        # и current_role - это то, чем он хочет пользоваться сейчас.
        # Доступные роли для переключения могут быть те же, или ограниченный список.
        # В простом варианте - показываем только текущую и основную.
        # Для более сложной логики (например, пользователь может быть и сотрудником и менеджером)
        # понадобится изменить модель UserProfile.
        # Пока покажем все возможные роли (это позволяет легко переключаться).
        available_roles = UserProfile.ROLE_CHOICES
        current_role = request.user.profile.current_role or request.user.profile.role
    else:
        available_roles = []
        current_role = None

    context = {
        'available_roles': available_roles,
        'current_role': current_role,
    }
    return render(request, 'core/switch_role.html', context)


@login_required
def schedule_view(request):
    """Просмотр графиков смен."""
    # Проверяем права доступа
    if not hasattr(request.user, 'profile'):
        messages.error(request, "Профиль пользователя не найден.")
        return redirect('dashboard')

    user_profile = request.user.profile
    current_role = user_profile.current_role or user_profile.role

    # Только менеджеры, планировщики и админы могут просматривать графики
    if current_role not in ['manager', 'planner', 'admin']:
        messages.error(request, "У вас нет доступа к этому разделу.")
        return redirect('dashboard')

    schedules = Schedule.objects.all()
    context = {
        'schedules': schedules,
    }
    return render(request, 'core/schedule_list.html', context)


@login_required
def optimization_view(request):
    """Страница оптимизации графиков."""
    # Проверяем права доступа
    if not hasattr(request.user, 'profile'):
        messages.error(request, "Профиль пользователя не найден.")
        return redirect('dashboard')

    user_profile = request.user.profile
    current_role = user_profile.current_role or user_profile.role

    # Только планировщики и админы могут использовать оптимизацию
    if current_role not in ['planner', 'admin']:
        messages.error(request, "У вас нет доступа к этому разделу.")
        return redirect('dashboard')

    # Получаем активные правила оптимизации
    rules = OptimizationRule.objects.filter(is_active=True)
    context = {
        'rules': rules,
    }
    return render(request, 'core/optimization.html', context)


# Простые заглушки для остальных страниц
@login_required
def employee_schedule(request):
    """График сотрудника (заглушка)."""
    return render(request, 'core/employee_schedule.html')

@login_required
def timeoff_requests(request):
    """Заявки на отгул (заглушка)."""
    return render(request, 'core/timeoff_requests.html')

@login_required
def shift_swaps(request):
    """Обмены сменами (заглушка)."""
    return render(request, 'core/shift_swaps.html')

@login_required
def reports(request):
    """Отчеты (заглушка)."""
    return render(request, 'core/reports.html')
