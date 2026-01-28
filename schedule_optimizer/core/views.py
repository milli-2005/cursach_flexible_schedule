# core/views.py
import secrets
import string
import json
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

from django.shortcuts import render
from .models import Schedule, ShiftAssignment
from collections import defaultdict

from django.shortcuts import redirect
from django.contrib import messages



logger = logging.getLogger(__name__)

def is_manager(user):
    """
    Проверяет, является ли пользователь руководителем.
    """
    if not hasattr(user, 'profile'):
        return False
    return user.profile.role == 'manager'


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


# core/views.py
from .forms import UserProfileEditForm

@login_required
def profile_edit(request):
    user = request.user
    profile = user.profile

    if request.method == 'POST':
        form = UserProfileEditForm(request.POST, instance=profile)
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



@login_required
def create_schedule_view(request):
    employees = UserProfile.objects.filter(role='employee')
    workout_types = WorkoutType.objects.all()

    # Генерация слотов
    start_hour, end_hour = 9, 21
    slots = []
    current_time = start_hour * 60
    while current_time + 50 <= end_hour * 60:
        start_str = f"{current_time // 60:02d}:{current_time % 60:02d}"
        current_time += 50
        end_str = f"{current_time // 60:02d}:{current_time % 60:02d}"
        slots.append((start_str, end_str))
        current_time += 10

    # Генерация дней (следующая неделя) — КАК СТРОКИ
    today = datetime.today()
    next_monday = today + timedelta(days=(7 - today.weekday()))
    current_days = [next_monday.date() + timedelta(days=i) for i in range(7)]

    # Строки для JS и шаблона
    date_strings = [d.strftime('%Y-%m-%d') for d in current_days]

    # Загрузка доступности
    availabilities = Availability.objects.filter(
        employee__in=employees,
        date__in=current_days
    )

    # Создаём SET для быстрой проверки в JS: "emp_id,date,time"
    availability_set = set()
    for a in availabilities:
        key = f"{a.employee.id},{a.date.strftime('%Y-%m-%d')},{a.start_time.strftime('%H:%M')}"
        availability_set.add(key)

    context = {
        'employees': employees,
        'workout_types': workout_types,
        'slots': slots,
         'days': current_days,
        'date_strings': date_strings,
        'availability_set_json': json.dumps(list(availability_set)),
    }
    return render(request, 'core/schedules/create_schedule.html', context)


from django.db.models import Count, Q


@login_required
def schedule_view(request):
    if not hasattr(request.user, 'profile'):
        messages.error(request, "Профиль пользователя не найден.")
        return redirect('dashboard')

    # Все сотрудники
    total_employees = UserProfile.objects.filter(role='employee').count()

    schedules = Schedule.objects.all().prefetch_related('approvals')

    # Добавляем аннотации
    schedules_with_stats = []
    for s in schedules:
        approved_count = s.approvals.filter(approved=True).count()
        rejected_count = s.approvals.filter(approved=False).count()
        responded_count = s.approvals.filter(approved__isnull=False).count()

        schedules_with_stats.append({
            'schedule': s,
            'total_employees': total_employees,
            'approved_count': approved_count,
            'rejected_count': rejected_count,
            'responded_count': responded_count,
        })

    context = {
        'schedules_with_stats': schedules_with_stats,
    }
    return render(request, 'core/schedules/schedule_list.html', context)


@login_required
def schedule_detail(request, schedule_id):
    schedule = get_object_or_404(Schedule, id=schedule_id)

    # === 1. Генерация дней из графика ===
    days = []
    current_date = schedule.start_date
    while current_date <= schedule.end_date:
        days.append(current_date)
        current_date += timedelta(days=1)

    # === 2. Генерация временных слотов (9:00–21:00) ===
    all_slots = []
    start_hour = 9
    end_hour = 21
    current_time = start_hour * 60  # в минутах
    end_time_total = end_hour * 60

    while current_time + 50 <= end_time_total:
        start = f"{current_time // 60:02d}:{current_time % 60:02d}"
        current_time += 50
        end = f"{current_time // 60:02d}:{current_time % 60:02d}"
        all_slots.append(f"{start}–{end}")
        current_time += 10

    # === 3. Загрузка всех назначений ОДНИМ запросом ===
    assignments = ShiftAssignment.objects.filter(
        schedule=schedule,
        date__in=days
    ).select_related('employee__user', 'workout_type')

    # === 4. Создание словаря: {(дата, время_начала): assignment} ===
    assignment_dict = {}
    for a in assignments:
        # Преобразуем время начала в строку "09:00"
        time_key = a.start_time.strftime('%H:%M')
        key = (a.date, time_key)
        assignment_dict[key] = a

    # === 5. Построение таблицы ===
    table_data = []
    for slot in all_slots:
        row = {'time_slot': slot, 'cells': []}
        start_time_str = slot.split('–')[0]  # Например, "09:00"

        for day in days:
            key = (day, start_time_str)
            assignment = assignment_dict.get(key)
            row['cells'].append({'assignment': assignment})
        table_data.append(row)

    context = {
        'schedule': schedule,
        'days': days,
        'table_data': table_data,
    }
    return render(request, 'core/schedules/view_schedule.html', context)


from collections import defaultdict
import json

@login_required
def edit_schedule_view(request, schedule_id):
    schedule = get_object_or_404(Schedule, id=schedule_id)

    # Генерация слотов (9:00–21:00)
    start_hour = 9
    end_hour = 21
    slots = []
    current_time = start_hour * 60
    end_time_total = end_hour * 60
    while current_time + 50 <= end_time_total:
        start = f"{current_time // 60:02d}:{current_time % 60:02d}"
        current_time += 50
        end = f"{current_time // 60:02d}:{current_time % 60:02d}"
        slots.append(f"{start} – {end}")
        current_time += 10

    # Генерация дней из графика
    from datetime import timedelta
    days = []
    current_date = schedule.start_date
    while current_date <= schedule.end_date:
        days.append(current_date)
        current_date += timedelta(days=1)

    date_strings = [d.strftime('%Y-%m-%d') for d in days]

    employees = UserProfile.objects.filter(role='employee')
    workout_types = WorkoutType.objects.all()

    # Текущие назначения
    assignments = ShiftAssignment.objects.filter(schedule=schedule).select_related('employee', 'workout_type')
    assignment_dict = defaultdict(dict)
    for a in assignments:
        time_key = a.start_time.strftime('%H:%M')
        assignment_dict[a.date][time_key] = a

    # === ЗАГРУЗКА ДОСТУПНОСТИ ДЛЯ АВТОЗАПОЛНЕНИЯ ===
    availabilities = Availability.objects.filter(
        employee__in=employees,
        date__in=days
    )
    availability_set = set()
    for a in availabilities:
        key = f"{a.employee.id},{a.date.strftime('%Y-%m-%d')},{a.start_time.strftime('%H:%M')}"
        availability_set.add(key)

    context = {
        'schedule': schedule,
        'slots': slots,
        'days': days,
        'date_strings': date_strings,  # ← для JS
        'employees': employees,
        'workout_types': workout_types,
        'assignment_dict': dict(assignment_dict),
        'availability_set_json': json.dumps(list(availability_set)),  # ← для JS
    }
    return render(request, 'core/schedules/edit_schedule.html', context)



@login_required
@user_passes_test(is_manager)
def delete_schedule_view(request, schedule_id):
    schedule = get_object_or_404(Schedule, id=schedule_id)
    if request.method == "POST":
        schedule_name = schedule.name
        schedule.delete()
        messages.success(request, f'График "{schedule_name}" успешно удалён.')
        return redirect('schedule_view')  # Перенаправление на список графиков
    # Если кто-то попытается GET — перенаправим на просмотр
    return redirect('view_schedule', schedule_id=schedule_id)




""" === ГРАФИК В ЛИЧНОМ КАБИНЕТЕ У ТРЕНЕРОВ === """
@login_required
def employee_schedule(request):
    user_profile = request.user.profile
    if user_profile.role != 'employee':
        messages.error(request, "Доступно только для сотрудников.")
        return redirect('dashboard')

    # Получаем все назначения текущего сотрудника
    assignments = ShiftAssignment.objects.filter(
        employee=user_profile
    ).select_related('schedule', 'workout_type').order_by('date', 'start_time')

    # Группируем по графикам
    schedules_dict = {}
    for a in assignments:
        key = a.schedule.id
        if key not in schedules_dict:
            schedules_dict[key] = {
                'schedule': a.schedule,
                'assignments': []
            }
        schedules_dict[key]['assignments'].append(a)

    # Добавляем флаг ответа
    schedules = []
    for item in schedules_dict.values():
        schedule = item['schedule']
        # Проверяем, отвечал ли сотрудник
        approval = ScheduleApproval.objects.filter(
            schedule=schedule,
            employee=user_profile
        ).first()
        has_responded = approval is not None and approval.approved is not None

        schedules.append({
            'schedule': schedule,
            'assignments': item['assignments'],
            'has_responded': has_responded,
            'approval': approval,
        })

    context = {
        'schedules': schedules,
    }
    return render(request, 'core/schedules/employee_schedule.html', context)




""" === ДОСТУПНОСТЬ === """

from django.utils import timezone
@login_required
def my_availability(request):
    # Получаем профиль текущего пользователя
    user_profile = request.user.profile

    if user_profile.role != 'employee':
        messages.error(request, "Доступно только для сотрудников.")
        return redirect('dashboard')

    #Определяем даты следующей недели
    today = datetime.today()
    # Находим ближайший ПОНЕДЕЛЬНИК следующей недели
    next_monday = today + timedelta(days=(7 - today.weekday()))
    # Создаём список из 7 дней: Пн, Вт, ..., Вс
    current_days = [next_monday + timedelta(days=i) for i in range(7)]
    # Также создаём список дат в виде строк (для удобства в шаблоне)
    date_strings = [d.strftime('%Y-%m-%d') for d in current_days]

    # Генерируем временные слоты
    start_hour, end_hour = 9, 21
    slots = []
    current_time = start_hour * 60  # Переводим в минуты
    while current_time + 50 <= end_hour * 60:
        start_str = f"{current_time // 60:02d}:{current_time % 60:02d}"
        current_time += 50
        end_str = f"{current_time // 60:02d}:{current_time % 60:02d}"
        slots.append((start_str, end_str))
        current_time += 10

    # Загружаем уже сохранённую доступность на эту неделю
    existing_avail = Availability.objects.filter(
        employee=user_profile,
        date__in=current_days  # Только дни этой недели
    )
    # Создаём множество ключей вида "2026-01-26_09:00" — это быстро и надёжно
    checked_keys = set()
    for a in existing_avail:
        key = f"{a.date.strftime('%Y-%m-%d')}_{a.start_time.strftime('%H:%M')}"
        checked_keys.add(key)

    # Подготавливаем данные для кнопки "Взять с прошлой недели"
    prev_monday = next_monday - timedelta(weeks=1)  # Понедельник ПРОШЛОЙ недели
    prev_days = [prev_monday + timedelta(days=i) for i in range(7)]
    # Загружаем доступность за прошлую неделю
    prev_avail = Availability.objects.filter(employee=user_profile, date__in=prev_days)
    prev_avail_list = []
    for a in prev_avail:
        # Сдвигаем дату на +1 неделю (чтобы применить к ТЕКУЩЕЙ неделе)
        new_date = a.date + timedelta(weeks=1)
        new_date_str = new_date.strftime('%Y-%m-%d')
        # Если такая дата есть в текущей неделе — добавляем в список
        if new_date_str in date_strings:
            prev_avail_list.append({
                'date': new_date_str,
                'time': a.start_time.strftime('%H:%M')
            })

    #Определяем, когда в последний раз обновлялась доступность
    last_updated = existing_avail.latest('updated_at').updated_at if existing_avail.exists() else None

    # Обработка формы при нажатии "Сохранить"
    if request.method == "POST":
        # Удаляем ВСЕ старые записи на эту неделю (чтобы не было дублей)
        Availability.objects.filter(employee=user_profile, date__in=current_days).delete()

        # Сохраняем новые отметки
        for day_obj in current_days:
            day_str = day_obj.strftime('%Y-%m-%d')
            for start_str, end_str in slots:
                # Имя чекбокса: slot_2026-01-26_09:00
                checkbox_name = f"slot_{day_str}_{start_str}"
                # Если чекбокс отмечен — создаём запись
                if request.POST.get(checkbox_name):
                    Availability.objects.create(
                        employee=user_profile,
                        date=day_obj,
                        start_time=datetime.strptime(start_str, '%H:%M').time(),
                        end_time=datetime.strptime(end_str, '%H:%M').time(),
                        is_available=True
                    )
        messages.success(request, "Ваша доступность успешно обновлена.")
        return redirect('my_availability')  # Перезагружаем страницу

    # === ШАГ 7: Передаём данные в шаблон ===
    context = {
        'days': current_days,  # объекты date — для красивого отображения (Пн, 26 янв)
        'date_strings': date_strings,  # строки дат — для работы с чекбоксами
        'slots': slots,  # список слотов (начало, конец)
        'checked_keys': checked_keys,  # множество строк вида "2026-01-26_09:00" — для checked
        'last_updated': last_updated,  # когда последний раз сохраняли
        'prev_avail_json': json.dumps(prev_avail_list),  # данные для JS-кнопки
    }
    return render(request, 'core/availability/my_availability.html', context)
