# core/views.py
import secrets
import string
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.http import JsonResponse
from .models import *
from .forms import UserInvitationForm
from django.contrib.auth.models import User
import logging
from django.utils import timezone #для времени сброса пароля
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404
from .models import Schedule, UserProfile, WorkoutType



logger = logging.getLogger(__name__)

def generate_random_password(length=12):
    """Генерирует случайный безопасный пароль."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password

def send_user_invitation(user, raw_password):
    """Отправляет приглашение новому пользователю с паролем."""
    subject = 'Приглашение в систему планирования смен'
    # HTML сообщение
    html_message = render_to_string('core/emails/user_invitation.html', {
        'user': user,
        'raw_password': raw_password,
        'site_url': 'http://localhost:8000',  # Замените на ваш домен
        'login_url': 'http://localhost:8000/login/',
    })

    # !!! ВАЖНО: ЗАМЕНИТЕ НА ВАШ ПУБЛИЧНЫЙ URL (например, от ngrok) !!! надо спросить вместе верхнего блоква
    # site_url = getattr(settings, 'PUBLIC_SITE_URL', 'http://localhost:8000')  # Используем переменную из settings
    # html_message = render_to_string('core/emails/user_invitation.html', {
    #     'user': user,
    #     'raw_password': raw_password,
    #     'site_url': site_url,
    #     'login_url': f'{site_url}/login/',
    #     'change_password_url': f'{site_url}/profile/change-password/'  # Ссылка на смену пароля
    # })


    # Текстовое сообщение (для клиентов без поддержки HTML)
    plain_message = strip_tags(html_message)

    # Отправляем email
    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email], # Отправляем на email нового пользователя
        html_message=html_message,
        fail_silently=False,
    )



def is_admin(user):
    """Проверяет, является ли пользователь администратором."""
    if not hasattr(user, 'profile'):
        return False
    return user.profile.role == 'manager' or user.is_superuser


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
                profile.position = form.cleaned_data.get('position', '')
                profile.phone = form.cleaned_data.get('phone', '')

                # УСТАНАВЛИВАЕМ ВРЕМЕННУЮ МЕТКУ
                profile.invitation_timestamp = timezone.now()
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



""" КРУДЫ ПОЛЬЗОВАТЕЛЕЙ"""
@login_required
@user_passes_test(is_admin)
def user_management(request):
    context = {}
    return render(request, 'core/dashboard/user_management.html', context)




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

            # УСТАНАВЛИВАЕМ ВРЕМЕННУЮ МЕТКУ ДЛЯ СБРОСА
            profile = user.profile
            profile.invitation_timestamp = timezone.now()
            profile.save()

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
        return render(request, 'profile/reset_password_confirm.html', context)
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
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()

            # Проверяем, не истёк ли срок действия временного пароля
            if hasattr(user, 'profile') and user.profile.is_temporary_password_expired():
                messages.error(request,
                               "Временный пароль устарел. Пожалуйста, свяжитесь с администратором для получения нового.")
                # Важно: не логиним пользователя, если пароль истёк
                return render(request, 'core/login.html', {'form': form})

            login(request, user)
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
    elif profile.role == 'studio_admin':
        # Для администратора студии
        # Здесь можно добавить логику для получения графиков, отчетов и т.д.
        schedules = Schedule.objects.all()[:5]  # Пример
        context['schedules'] = schedules
        return render(request, 'core/dashboard/dashboard_studio_admin.html', context)
    elif profile.role == 'manager':
        # Для менеджера
        schedules = Schedule.objects.all()[:5]  # Пример
        context['schedules'] = schedules
        return render(request, 'core/dashboard/dashboard_manager.html', context)
    else:
        # На всякий случай, если роль неизвестна
        messages.error(request, "Неизвестная роль пользователя.")
        return redirect('index')


# # core/views.py
# @login_required
# def dashboard(request):
#     user = request.user
#     profile = user.profile
#     # Просто рендерим базовый шаблон с минимальным содержимым
#     context = {
#         'user': user,
#         'profile': profile,
#     }
#     return render(request, 'core/debug_dashboard.html', context)


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
    from .forms import UserProfileEditForm  # Импортируем форму редактирования
    user = request.user
    profile = user.profile  # Предполагается, что профиль всегда существует

    if request.method == 'POST':
        form = UserProfileEditForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль успешно обновлён.")
            return redirect('profile_view')  # Перенаправляем на просмотр после сохранения
    else:
        form = UserProfileEditForm(instance=profile)

    context = {
        'form': form,
    }
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
        return redirect('login') # Или на главную, если не хочет логиниться снова

    if request.method == 'POST':
        form = SetPasswordForm(user, request.POST)  # Передаём текущего пользователя
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Важно: обновляем сессию, чтобы пользователь не вышел

            # СБРАСЫВАЕМ ВРЕМЕННУЮ МЕТКУ ПОСЛЕ УСПЕШНОЙ СМЕНЫ ПАРОЛЯ
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
def schedule_view(request):
    """Просмотр графиков смен."""

    # Проверяем права доступа
    if not hasattr(request.user, 'profile'):
        messages.error(request, "Профиль пользователя не найден.")
        return redirect('dashboard')

    user_profile = request.user.profile
    current_role = user_profile.role  # Берём роль из профиля

    # Только менеджеры, планировщики и админы могут просматривать графики
    if current_role not in ['studio_admin', 'manager']:
        messages.error(request, "У вас нет доступа к этому разделу.")
        return redirect('dashboard')

    schedules = Schedule.objects.all()
    context = {
        'schedules': schedules,
    }
    return render(request, 'core/schedules/schedule_list.html', context)


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
    if current_role not in ['manager']:
        messages.error(request, "У вас нет доступа к этому разделу.")
        return redirect('dashboard')

    rules = OptimizationRule.objects.filter(is_active=True)
    context = {
        'rules': rules,
    }
    return render(request, 'core/optimization.html', context)



@login_required
def employee_schedule(request):
    if not hasattr(request.user, 'profile'):
        messages.error(request, "Профиль пользователя не найден.")
        return redirect('dashboard')

    user_profile = request.user.profile
    current_role = user_profile.role # Берём роль из профиля

    # Права доступа могут отличаться для сотрудника и админа студии
    # Например, сотрудник видит только свой график, админ студии - всех
    context = {
        'current_role': current_role,
    }
    return render(request, 'core/employee_schedule.html', context)



@login_required
def timeoff_requests(request):
    if not hasattr(request.user, 'profile'):
        messages.error(request, "Профиль пользователя не найден.")
        return redirect('dashboard')

    user_profile = request.user.profile
    current_role = user_profile.role # Берём роль из профиля

    # Права доступа могут отличаться
    # Сотрудник видит свои заявки, менеджер - все на согласование
    context = {
        'current_role': current_role,
    }
    return render(request, 'core/timeoff_requests.html', context)



@login_required
def shift_swaps(request):
    if not hasattr(request.user, 'profile'):
        messages.error(request, "Профиль пользователя не найден.")
        return redirect('dashboard')

    user_profile = request.user.profile
    current_role = user_profile.role # Берём роль из профиля

    # Права доступа могут отличаться
    context = {
        'current_role': current_role,
    }
    return render(request, 'core/shift_swaps.html', context)



@login_required
def reports(request):
    if not hasattr(request.user, 'profile'):
        messages.error(request, "Профиль пользователя не найден.")
        return redirect('dashboard')

    user_profile = request.user.profile
    current_role = user_profile.role # Берём роль из профиля

    if current_role not in ['studio_admin', 'manager']:
        messages.error(request, "У вас нет доступа к этому разделу.")
        return redirect('dashboard')

    # Здесь будет логика генерации отчетов
    context = {}
    return render(request, 'core/reports.html', context)


def dashboard_employee(request):
    # Логика для дашборда сотрудника
    return render(request, 'core/dashboard_employee.html')

def dashboard_studio_admin(request):
    # Логика для дашборда админа студии
    return render(request, 'core/dashboard_studio_admin.html')

def dashboard_manager(request):
    # Логика для дашборда менеджера
    return render(request, 'core/dashboard_manager.html')

@login_required
def workout_types(request):
    """
    Страница управления типами занятий.
    Доступна только руководителю.
    """
    return render(request, 'core/workouts/workout_types.html')


from datetime import datetime, timedelta
from django.shortcuts import render
from .models import UserProfile, WorkoutType


@login_required
def create_schedule_view(request):
    """
    Страница для ручного создания/редактирования графика.
    """
    # Получаем всех сотрудников (тренеров и администраторов)
    employees = UserProfile.objects.filter(role='employee')

    # Получаем все типы занятий
    workout_types = WorkoutType.objects.all()

    # Генерируем временные слоты (с 9:00 до 22:00)
    start_hour = 9
    end_hour = 22
    slots = []
    current_time = start_hour * 60  # в минутах
    end_time_total = end_hour * 60

    while current_time + 50 <= end_time_total:
        start = f"{current_time // 60:02d}:{current_time % 60:02d}"
        current_time += 50  # 50 минут занятие
        end = f"{current_time // 60:02d}:{current_time % 60:02d}"
        slots.append(f"{start}–{end}")
        current_time += 10  # 10 минут перерыв

    # Генерируем дни недели (следующая неделя)
    today = datetime.today()
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=1)
    days = []
    for i in range(7):
        date = start_of_week + timedelta(days=i)
        days.append({
            'date': date.date(),
            'name': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][i]
        })

    context = {
        'employees': employees,
        'workout_types': workout_types,
        'slots': slots,
        'days': days,
    }
    return render(request, 'core/schedules/create_schedule.html', context)