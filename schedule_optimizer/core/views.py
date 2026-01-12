"""
Представления (обработчики запросов) для приложения core.
Здесь обрабатываем логику страниц.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from .models import *
import logging

"""
Представления для приглашения пользователей.
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import User
from .forms import UserInvitationForm
from .utils import generate_random_password, send_user_invitation
import logging

logger = logging.getLogger(__name__)


def is_admin(user):
    """Проверяет, является ли пользователь администратором."""
    if not hasattr(user, 'profile'):
        return False
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
                    password=raw_password,
                    first_name=form.cleaned_data.get('first_name', ''),
                    last_name=form.cleaned_data.get('last_name', ''),
                )

                # Создаем профиль пользователя
                from .models import UserProfile
                profile = UserProfile.objects.get(user=user)
                profile.role = form.cleaned_data['role']
                profile.department = form.cleaned_data.get('department', '')
                profile.position = form.cleaned_data.get('position', '')
                profile.phone = form.cleaned_data.get('phone', '')
                profile.save()

                # Отправляем приглашение на email
                try:
                    send_user_invitation(user, raw_password)
                    messages.success(
                        request,
                        f'Пользователь {user.username} успешно создан. '
                        f'Приглашение отправлено на {user.email}.'
                    )

                    # Логируем действие
                    logger.info(f'Администратор {request.user.username} создал пользователя {user.username}')

                except Exception as e:
                    # Если email не отправился, все равно создаем пользователя
                    # и показываем пароль администратору
                    messages.warning(
                        request,
                        f'Пользователь {user.username} создан, но email не отправлен. '
                        f'Ошибка: {str(e)}. Пароль пользователя: {raw_password}'
                    )
                    logger.error(f'Ошибка отправки email для пользователя {user.username}: {str(e)}')

                return redirect('user_management')

            except Exception as e:
                messages.error(request, f'Ошибка при создании пользователя: {str(e)}')
                logger.error(f'Ошибка создания пользователя: {str(e)}')
    else:
        form = UserInvitationForm()

    return render(request, 'core/invite_user.html', {'form': form})


@login_required
@user_passes_test(is_admin)
def user_management(request):
    """
    Страница управления пользователями для администратора.
    """
    users = User.objects.all().select_related('profile')

    context = {
        'users': users,
    }
    return render(request, 'core/user_management.html', context)


@login_required
@user_passes_test(is_admin)
def reset_user_password(request, user_id):
    """
    Сброс пароля пользователя и отправка нового на email.
    """
    try:
        user = User.objects.get(id=user_id)

        if request.method == 'POST':
            # Генерируем новый случайный пароль
            raw_password = generate_random_password()

            # Устанавливаем новый пароль
            user.set_password(raw_password)
            user.save()

            # Отправляем email с новым паролем
            try:
                send_user_invitation(user, raw_password)
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

            # Устанавливаем текущую роль из профиля
            if hasattr(user, 'profile'):
                request.session['current_role'] = user.profile.current_role

            messages.success(request, f"Добро пожаловать, {user.username}!")
            return redirect('index')
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
                pass

        elif role == 'manager':
            # Для менеджера показываем его команду и смены
            pass

        elif role == 'planner':
            # Для планировщика показываем графики и инструменты оптимизации
            schedules = Schedule.objects.all()[:5]
            context['schedules'] = schedules

        elif role == 'admin':
            # Для админа показываем статистику системы
            user_count = User.objects.count()
            context['user_count'] = user_count

    return render(request, 'core/dashboard.html', context)


@login_required
def profile_view(request):
    """Страница профиля пользователя."""
    user = request.user
    context = {
        'user': user,
    }
    return render(request, 'core/profile.html', context)


@login_required
def switch_role(request):
    """Смена текущей роли пользователя."""
    if request.method == 'POST':
        new_role = request.POST.get('role')
        if new_role in dict(UserProfile.ROLE_CHOICES):
            if hasattr(request.user, 'profile'):
                request.user.profile.current_role = new_role
                request.user.profile.save()
                request.session['current_role'] = new_role
                messages.success(request, f"Роль изменена на {request.user.profile.get_current_role_display()}")
            else:
                messages.error(request, "Профиль пользователя не найден.")
        return redirect('index')

    # GET запрос - показываем форму выбора роли
    if hasattr(request.user, 'profile'):
        # Получаем все роли пользователя (в простой реализации - одна роль)
        # В расширенной версии здесь можно получить список доступных ролей
        available_roles = [(request.user.profile.role, request.user.profile.get_role_display())]
    else:
        available_roles = []

    context = {
        'available_roles': available_roles,
    }
    return render(request, 'core/switch_role.html', context)


@login_required
def schedule_view(request):
    """Просмотр графиков смен."""
    # Проверяем права доступа
    if not hasattr(request.user, 'profile'):
        messages.error(request, "Профиль пользователя не найден.")
        return redirect('index')

    user_profile = request.user.profile
    current_role = user_profile.current_role or user_profile.role

    # Только менеджеры и планировщики могут просматривать графики
    if current_role not in ['manager', 'planner', 'admin']:
        messages.error(request, "У вас нет доступа к этому разделу.")
        return redirect('index')

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
        return redirect('index')

    user_profile = request.user.profile
    current_role = user_profile.current_role or user_profile.role

    # Только планировщики могут использовать оптимизацию
    if current_role not in ['planner', 'admin']:
        messages.error(request, "У вас нет доступа к этому разделу.")
        return redirect('index')

    # Получаем правила оптимизации
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