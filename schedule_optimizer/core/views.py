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

# core/views.py
from datetime import datetime, timedelta
@login_required
def my_availability(request):
    user_profile = request.user.profile
    if user_profile.role != 'employee':
        messages.error(request, "Доступно только для сотрудников.")
        return redirect('dashboard')

    # === ОБРАБОТКА POST: сохранение данных ===
    if request.method == "POST":
        week_str = request.POST.get('selected_week')
        if week_str:
            try:
                week_start = datetime.strptime(week_str, '%Y-%m-%d').date()
                if week_start.weekday() != 0:
                    week_start = week_start - timedelta(days=week_start.weekday())
            except (ValueError, TypeError):
                messages.error(request, "Неверный формат даты.")
                return redirect('my_availability')
        else:
            today = datetime.today()
            days_ahead = (7 - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            week_start = today + timedelta(days=days_ahead)

        # Генерация дней
        current_days = [week_start + timedelta(days=i) for i in range(7)]
        date_strings = [d.strftime('%Y-%m-%d') for d in current_days]

        # Слоты
        start_hour, end_hour = 9, 21
        slots = []
        current_time = start_hour * 60
        while current_time + 50 <= end_hour * 60:
            start_str = f"{current_time // 60:02d}:{current_time % 60:02d}"
            current_time += 50
            end_str = f"{current_time // 60:02d}:{current_time % 60:02d}"
            slots.append((start_str, end_str))
            current_time += 10

        print("=== POST KEYS ===")
        print(list(request.POST.keys()))
        print("=== EXPECTED SAMPLE ===")
        print(f"Sample key: {date_strings[0]}_{slots[0][0]}")

        # Удаление старых записей
        Availability.objects.filter(
            employee=user_profile,
            date__in=current_days
        ).delete()

        # Сохранение новых
        new_records = []
        for day_str in date_strings:
            for slot_start, slot_end in slots:
                key = f"{day_str}_{slot_start}"
                if request.POST.get(key) == 'on':  # ← ИЗМЕНЕНО
                    date_obj = datetime.strptime(day_str, '%Y-%m-%d').date()
                    start_time = datetime.strptime(slot_start, '%H:%M').time()
                    end_time = datetime.strptime(slot_end, '%H:%M').time()
                    new_records.append(Availability(
                        employee=user_profile,
                        date=date_obj,
                        start_time=start_time,
                        end_time=end_time,
                        is_available=True
                    ))

        if new_records:
            Availability.objects.bulk_create(new_records)
            messages.success(request, "Доступность успешно сохранена!")
        else:
            messages.info(request, "Доступность не указана.")

        return redirect(f"{request.path}?week={week_start.strftime('%Y-%m-%d')}")

    # === ОБРАБОТКА GET: отображение формы ===
    today = datetime.today()
    days_ahead = (7 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    default_week_start = today + timedelta(days=days_ahead)

    week_start = default_week_start
    week_param = request.GET.get('week')
    if week_param:
        try:
            parsed_date = datetime.strptime(week_param, '%Y-%m-%d').date()
            week_start = parsed_date - timedelta(days=parsed_date.weekday())
        except (ValueError, TypeError):
            pass

    # Генерация дней (без спискового включения — через цикл)
    current_days = []
    for i in range(7):
        current_days.append(week_start + timedelta(days=i))
    date_strings = [d.strftime('%Y-%m-%d') for d in current_days]

    # Слоты
    start_hour, end_hour = 9, 21
    slots = []
    current_time = start_hour * 60
    while current_time + 50 <= end_hour * 60:
        hour = current_time // 60
        minute = current_time % 60
        start_str = f"{hour:02d}:{minute:02d}"
        current_time += 50
        end_str = f"{current_time // 60:02d}:{current_time % 60:02d}"
        slots.append((start_str, end_str))
        current_time += 10

    # Загрузка данных
    availabilities = Availability.objects.filter(
        employee=user_profile,
        date__in=current_days
    )
    checked_keys = set()
    for a in availabilities:
        key = f"{a.date.strftime('%Y-%m-%d')}_{a.start_time.strftime('%H:%M')}"
        checked_keys.add(key)

    last_updated = availabilities.order_by('-updated_at').first()

    # === ДАННЫЕ С ПРОШЛОЙ НЕДЕЛИ ДЛЯ JS ===
    prev_week_start = week_start - timedelta(weeks=1)
    prev_avail = Availability.objects.filter(
        employee=user_profile,
        date__gte=prev_week_start,
        date__lt=week_start
    )
    prev_avail_list = []
    for a in prev_avail:
        # Сдвигаем дату на неделю вперёд
        new_date = a.date + timedelta(weeks=1)
        prev_avail_list.append({
            'date': new_date.strftime('%Y-%m-%d'),
            'time': a.start_time.strftime('%H:%M')
        })

    prev_week = (week_start - timedelta(weeks=1)).strftime('%Y-%m-%d')
    next_week = (week_start + timedelta(weeks=1)).strftime('%Y-%m-%d')

    context = {
        'days': current_days,
        'date_strings': date_strings,
        'slots': slots,
        'checked_keys': checked_keys,
        'last_updated': last_updated,
        'week_start': week_start,
        'week_end': week_start + timedelta(days=6),
        'prev_week': prev_week,
        'next_week': next_week,
        'prev_avail_json': json.dumps(prev_avail_list),
    }
    return render(request, 'core/availability/my_availability.html', context)


#для отправки напоминаний о доступности
@login_required
@user_passes_test(lambda u: u.profile.role == 'manager')
def send_availability_reminder_manual(request):
    if request.method == "POST":
        employees = UserProfile.objects.filter(role='employee')
        emails = [emp.user.email for emp in employees if emp.user.email]
        if emails:
            send_mail(
                subject="Напоминание: укажите ваши рабочие часы",
                message="Пожалуйста, зайдите в личный кабинет и укажите, когда вы можете работать на следующей неделе.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=emails,
                fail_silently=False,
            )
            messages.success(request, f"Напоминание отправлено {len(emails)} сотрудникам.")
        else:
            messages.warning(request, "Нет сотрудников с email.")
    return redirect('schedule_view')



""" === ОТЧЕТЫ === """
import json
from datetime import date, datetime, timedelta
from collections import defaultdict
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import ShiftAssignment, UserProfile, WorkoutType

@login_required
def reports_view(request):
    if request.user.profile.role != 'manager':
        messages.error(request, "Доступ запрещён.")
        return redirect('dashboard')

    # === ПОЛУЧЕНИЕ СТАВКИ ИЗ КУКИ ===
    hour_rate = request.COOKIES.get('hour_rate')
    if hour_rate:
        try:
            hour_rate = float(hour_rate)
        except ValueError:
            hour_rate = None

    # === ОБРАБОТКА СОХРАНЕНИЯ СТАВКИ ===
    if 'set_hour_rate' in request.GET:
        new_rate_str = request.GET.get('hour_rate', '').strip()
        if new_rate_str:
            try:
                new_rate = float(new_rate_str)
                if new_rate >= 0:
                    hour_rate = new_rate
                    messages.success(request, f"Ставка сохранена: {int(hour_rate)} ₽/час")
                else:
                    messages.error(request, "Ставка не может быть отрицательной")
            except ValueError:
                messages.error(request, "Введите корректное число")
        else:
            hour_rate = None
            messages.info(request, "Ставка сброшена")

    # === ОБРАБОТКА СБРОСА ===
    if 'reset_rate' in request.GET:
        hour_rate = None
        messages.info(request, "Ставка сброшена")

    # === ПАРАМЕТРЫ ФИЛЬТРАЦИИ ===
    period = request.GET.get('period', 'month')
    employee_id = request.GET.get('employee')
    workout_id = request.GET.get('workout')
    search_query = request.GET.get('search', '').strip()

    today = date.today()
    if period == 'week':
        start_date = today - timedelta(days=7)
        end_date = today
    elif period == 'month':
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(month=12, day=31)
    else:
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

    delta = end_date - start_date
    all_dates = [start_date + timedelta(days=i) for i in range(delta.days + 1)]

    all_employees = UserProfile.objects.filter(role='employee').order_by('user__username')
    employees = all_employees

    assignments = ShiftAssignment.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).select_related('employee', 'workout_type')

    if employee_id and employee_id != 'all':
        assignments = assignments.filter(employee_id=employee_id)
        employees = employees.filter(id=employee_id)
    if workout_id and workout_id != 'all':
        assignments = assignments.filter(workout_type_id=workout_id)
    if search_query:
        assignments = assignments.filter(
            Q(employee__user__username__icontains=search_query) |
            Q(workout_type__name__icontains=search_query)
        )

    # === АГРЕГАЦИЯ ===
    data = defaultdict(lambda: defaultdict(float))
    emp_hours = defaultdict(float)
    day_hours = [0.0] * 7
    workout_hours = defaultdict(float)
    date_hours = defaultdict(float)

    for a in assignments:
        dur = (datetime.combine(date.min, a.end_time) - datetime.combine(date.min, a.start_time)).total_seconds() / 3600
        data[a.employee_id][a.date] += dur
        emp_hours[a.employee.user.username] += dur
        day_hours[a.date.weekday()] += dur
        workout_hours[a.workout_type.name] += dur
        date_hours[a.date] += dur

    total_hours = {}
    total_shifts = {}
    for emp in employees:
        emp_id = emp.id
        hours = sum(data[emp_id].values())
        shifts = len([h for h in data[emp_id].values() if h > 0])
        total_hours[emp.id] = round(hours, 2)
        total_shifts[emp.id] = shifts

    # === СУММА ПО ДНЯМ (для "Итого по дням") ===
    daily_totals = []
    for d in all_dates:
        total = sum(data[emp.id].get(d, 0) for emp in employees)
        daily_totals.append(int(total))

    # === ОБЩАЯ ЗП ===
    total_salary = 0
    if hour_rate is not None:
        total_salary = int(sum(total_hours.values()) * hour_rate)

    # === ГРАФИКИ ===
    chart_data = {
        'empNames': list(emp_hours.keys()) or [],
        'empValues': [round(v, 2) for v in emp_hours.values()] or [],
        'dayLabels': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
        'dayValues': [round(v, 2) for v in day_hours] or [0]*7,
        'workoutLabels': list(workout_hours.keys()) or [],
        'workoutValues': [round(v, 2) for v in workout_hours.values()] or [],
        'dateLabels': [d.strftime('%d.%m') for d in sorted(date_hours.keys())] or [],
        'dateValues': [round(date_hours[d], 2) for d in sorted(date_hours.keys())] or [],
    }

    context = {
        'period': period,
        'employee_id': employee_id or 'all',
        'workout_id': workout_id or 'all',
        'search_query': search_query,
        'employees': employees,
        'all_employees': all_employees,
        'workout_types': WorkoutType.objects.all(),
        'all_dates': all_dates,
        'data': data,
        'total_hours': total_hours,
        'total_shifts': total_shifts,
        'daily_totals': daily_totals,
        'total_all_hours': round(sum(total_hours.values()), 2),
        'total_all_assignments': assignments.count(),
        'active_employees': len(employees),
        'chart_data_json': json.dumps(chart_data, ensure_ascii=False),
        'hour_rate': hour_rate,
        'total_salary': total_salary,
    }

    # === ОТВЕТ ===
    resp = render(request, 'core/reports/reports.html', context)

    # === СОХРАНЕНИЕ В КУКИ ===
    if 'set_hour_rate' in request.GET or 'reset_rate' in request.GET:
        if hour_rate is not None:
            resp.set_cookie('hour_rate', str(hour_rate), max_age=365*24*60*60)  # 1 год
        else:
            resp.delete_cookie('hour_rate')

    return resp


#ЭКСПОРТ ФАЙЛОВ
# from openpyxl import Workbook
# from django.http import HttpResponse
#
# @login_required
# def export_report_detailed(request):
#     if request.user.profile.role != 'manager':
#         return redirect('dashboard')
#
#     period = request.GET.get('period', 'week')
#     today = datetime.today().date()
#
#     if period == 'week':
#         start_date = today - timedelta(days=7)
#     elif period == 'month':
#         start_date = today - timedelta(days=30)
#     elif period == 'year':
#         start_date = today - timedelta(days=365)
#     else:
#         start_date = today - timedelta(days=7)
#
#     assignments = ShiftAssignment.objects.filter(
#         date__date__gte=start_date,
#         date__date__lte=today
#     ).select_related('employee__user', 'workout_type', 'schedule')
#
#     wb = Workbook()
#     ws = wb.active
#     ws.title = "Аналитика"
#
#     headers = ["Сотрудник", "Дата", "Время", "Тип", "Часов", "График"]
#     ws.append(headers)
#
#     for a in assignments.order_by('-date', 'start_time'):
#         dur = (datetime.combine(date.min, a.end_time) - datetime.combine(date.min, a.start_time)).total_seconds() / 3600
#         ws.append([
#             a.employee.user.username,
#             a.date.strftime('%d.%m.%Y'),
#             f"{a.start_time.strftime('%H:%M')}-{a.end_time.strftime('%H:%M')}",
#             a.workout_type.name,
#             round(dur, 2),
#             a.schedule.name if a.schedule else "-"
#         ])
#
#     response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
#     response['Content-Disposition'] = f'attachment; filename=analytics_{period}_{today.strftime("%Y%m%d")}.xlsx'
#     wb.save(response)
#     return response




#для документа кто сколько работал
# from datetime import date, datetime, timedelta
# from collections import defaultdict
#
# @login_required
# def operational_report(request):
#     if request.user.profile.role != 'manager':
#         messages.error(request, "Доступ запрещён.")
#         return redirect('dashboard')
#
#     # Выбор периода
#     period = request.GET.get('period', 'month')
#     today = date.today()
#
#     if period == 'week':
#         start_date = today - timedelta(days=7)
#     elif period == 'month':
#         start_date = today.replace(day=1)
#     elif period == 'year':
#         start_date = today.replace(month=1, day=1)
#     else:
#         start_date = today.replace(day=1)
#
#     # Определяем конец периода
#     if period == 'week':
#         end_date = today
#     elif period == 'month':
#         # Последний день месяца
#         if today.month == 12:
#             end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
#         else:
#             end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
#     elif period == 'year':
#         end_date = today.replace(year=today.year, month=12, day=31)
#     else:
#         end_date = today
#
#     # Все даты в периоде
#     delta = end_date - start_date
#     all_dates = [start_date + timedelta(days=i) for i in range(delta.days + 1)]
#
#     # Сотрудники
#     employees = UserProfile.objects.filter(role='employee').order_by('user__username')
#
#     # Загружаем назначения
#     assignments = ShiftAssignment.objects.filter(
#         date__date__gte=start_date,
#         date__date__lte=end_date
#     ).select_related('employee', 'workout_type')
#
#     # Собираем данные: employee -> date -> hours
#     data = defaultdict(lambda: defaultdict(float))  # {emp_id: {date: hours}}
#     for a in assignments:
#         dur = (datetime.combine(date.min, a.end_time) - datetime.combine(date.min, a.start_time)).total_seconds() / 3600
#         data[a.employee_id][a.date] += dur
#
#     # Подготавливаем для шаблона
#     rows = []
#     total_hours_per_day = [0.0] * len(all_dates)
#     total_shifts_per_day = [0] * len(all_dates)
#
#     for emp in employees:
#         row = {
#             'employee': emp,
#             'hours': [],
#             'total': 0.0,
#         }
#         for i, d in enumerate(all_dates):
#             h = data[emp.id].get(d, 0.0)
#             row['hours'].append(round(h, 1) if h > 0 else '')
#             row['total'] += h
#             total_hours_per_day[i] += h
#             if h > 0:
#                 total_shifts_per_day[i] += 1
#         rows.append(row)
#
#     # Итоговая строка
#     total_row = {
#         'employee': {'user': {'username': 'Итого кол-часов'}},
#         'hours': [round(h, 1) for h in total_hours_per_day],
#         'total': round(sum(total_hours_per_day), 1)
#     }
#
#     context = {
#         'period': period,
#         'start_date': start_date,
#         'end_date': end_date,
#         'all_dates': all_dates,
#         'rows': rows,
#         'total_row': total_row,
#         'total_shifts_per_day': total_shifts_per_day,
#     }
#     return render(request, 'core/reports/operational.html', context)


from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Border, Side
from openpyxl.utils import get_column_letter
from django.http import HttpResponse
from datetime import date, timedelta, datetime
from .models import ShiftAssignment, UserProfile

def _format_number(value):
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return round(value, 1) if isinstance(value, float) else value

@login_required
def export_operational_excel(request):
    if request.user.profile.role != 'manager':
        return redirect('dashboard')

    period = request.GET.get('period', 'month')
    today = date.today()

    # Определяем период
    if period == 'week':
        start_date = today - timedelta(days=7)
        end_date = today
    elif period == 'month':
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(month=12, day=31)
    else:
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

    # Все даты периода
    all_dates = []
    d = start_date
    while d <= end_date:
        all_dates.append(d)
        d += timedelta(days=1)

    employees = UserProfile.objects.filter(role='employee').order_by('user__username')

    assignments = ShiftAssignment.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).select_related('employee')

    from collections import defaultdict
    data = defaultdict(lambda: defaultdict(float))
    for a in assignments:
        dur = (datetime.combine(date.min, a.end_time) - datetime.combine(date.min, a.start_time)).total_seconds() / 3600
        data[a.employee_id][a.date] += dur

    # Ставка из куки
    hour_rate = request.COOKIES.get('hour_rate')
    if hour_rate:
        try:
            hour_rate = float(hour_rate)
        except:
            hour_rate = None
    else:
        hour_rate = None

    # Подсчёт
    total_hours_per_emp = {}
    total_salary_per_emp = {}
    for emp in employees:
        emp_id = emp.id
        hours = sum(data[emp_id].values())
        total_hours_per_emp[emp.id] = _format_number(hours)
        salary = hours * hour_rate if hour_rate else 0
        total_salary_per_emp[emp.id] = _format_number(salary)

    # === EXCEL ===
    wb = Workbook()
    ws = wb.active
    ws.title = "Табель"

    # Граница: все ячейки — тонкая рамка
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # Ширина столбцов
    ws.column_dimensions['A'].width = 25          # Сотрудник — широкий
    ws.column_dimensions['B'].width = 14          # Период
    ws.column_dimensions['C'].width = 10          # ЗП
    for i in range(len(all_dates)):
        col_letter = get_column_letter(4 + i)      # D = 4
        ws.column_dimensions[col_letter].width = 6  # Узкие дни, но чуть шире для читаемости

    # Заголовки (строка 1)
    ws.cell(row=1, column=1, value="Сотрудник")
    period_label = f"{start_date.day}-{end_date.day} {start_date.strftime('%B')}"
    ws.cell(row=1, column=2, value=period_label)
    ws.cell(row=1, column=3, value="ЗП")

    # Даты: "01.01", "02.01"...
    for i, d in enumerate(all_dates, start=4):  # D = 4
        ws.cell(row=1, column=i, value=f"{d.day:02d}.{d.month:02d}")

    # ЖИРНЫЙ шрифт для всей первой строки
    bold_font = Font(bold=True)
    for col in range(1, 4 + len(all_dates)):
        cell = ws.cell(row=1, column=col)
        cell.font = bold_font
        cell.border = thin_border

    # Заливка заголовков B и C — зелёная
    green_fill = PatternFill(start_color="0099FF00", end_color="0099FF00", fill_type="solid")
    for col in [2, 3]:
        ws.cell(row=1, column=col).fill = green_fill

    # Данные по сотрудникам
    for row_idx, emp in enumerate(employees, start=2):
        ws.cell(row=row_idx, column=1, value=emp.user.username)
        ws.cell(row=row_idx, column=2, value=total_hours_per_emp[emp.id])
        ws.cell(row=row_idx, column=3, value=total_salary_per_emp[emp.id])

        # Зелёная заливка для B и C
        for col in [2, 3]:
            cell = ws.cell(row=row_idx, column=col)
            cell.fill = green_fill
            cell.border = thin_border

        # Дни: без нулей, с границами
        for i, d in enumerate(all_dates, start=4):
            h = data[emp.id].get(d, 0)
            val = _format_number(h) if h != 0 else ""
            cell = ws.cell(row=row_idx, column=i, value=val)
            cell.border = thin_border

    # ИТОГОВАЯ СТРОКА
    last_row = len(employees) + 2
    ws.cell(row=last_row, column=1, value="Итого кол-часов")

    total_hours_all = sum(total_hours_per_emp.values())
    total_salary_all = sum(total_salary_per_emp.values())

    ws.cell(row=last_row, column=2, value=_format_number(total_hours_all))
    ws.cell(row=last_row, column=3, value=_format_number(total_salary_all))

    # Дни — сумма
    for i, d in enumerate(all_dates, start=4):
        total_day = sum(data[emp.id].get(d, 0) for emp in employees)
        val = _format_number(total_day) if total_day != 0 else ""
        cell = ws.cell(row=last_row, column=i, value=val)
        cell.border = thin_border

    # Форматирование итоговой строки
    yellow_fill = PatternFill(start_color="FFFFCC", end_color="FFFFCC", fill_type="solid")
    purple_font = Font(color="800080", bold=True)

    for col in range(1, 4 + len(all_dates)):
        cell = ws.cell(row=last_row, column=col)
        cell.fill = yellow_fill
        cell.font = purple_font
        cell.border = thin_border

    # Применяем границы ко ВСЕМ ячейкам таблицы (включая внутренние)
    max_row = last_row
    max_col = 3 + len(all_dates)
    for row in range(1, max_row + 1):
        for col in range(1, max_col + 1):
            cell = ws.cell(row=row, column=col)
            if not cell.border:
                cell.border = thin_border

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=tabel_{period}_{today.strftime("%Y%m%d")}.xlsx'
    wb.save(response)
    return response