# core/api_views/user_views.py
import logging
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User
from django.db.models import Count
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from core.models import UserProfile, Employee  # ← ЕДИНСТВЕННЫЙ ПРАВИЛЬНЫЙ ИМПОРТ
from core.forms import UserInvitationForm
import json
import secrets
import string
from django.views.decorators.http import require_http_methods
from core.models import WorkoutType


logger = logging.getLogger(__name__)

def is_admin(user):
    if not hasattr(user, 'profile'):
        return False
    return user.profile.role == 'manager' or user.is_superuser

def generate_random_password(length=12):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def send_user_invitation(user, raw_password):
    subject = 'Приглашение в систему планирования смен'
    site_url = getattr(settings, 'PUBLIC_SITE_URL', 'http://localhost:8000')
    html_message = render_to_string('core/emails/user_invitation.html', {
        'user': user,
        'raw_password': raw_password,
        'site_url': site_url,
        'login_url': f'{site_url}/login/',
        'change_password_url': f'{site_url}/profile/change-password/'
    })
    plain_message = strip_tags(html_message)

    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f"Ошибка отправки email для {user.username}: {e}")

@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET"])
def api_get_users(request):
    users = User.objects.select_related('profile').all().order_by('username')
    workout_count_map = {
        row['user_profile_id']: row['workout_count']
        for row in Employee.objects.values('user_profile_id').annotate(workout_count=Count('workout_types'))
    }
    data = []
    for u in users:
        profile = u.profile
        workout_count = workout_count_map.get(profile.id, 0)
        has_workout_types = workout_count > 0
        data.append({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'first_name': u.first_name or '',
            'last_name': u.last_name or '',
            'profile': {
                'role': profile.role,
                'role_display': dict(UserProfile.ROLE_CHOICES).get(profile.role, profile.role),
                'phone': profile.phone or '',
                'patronymic': profile.patronymic or '',
                'workout_count': workout_count if profile.role == 'employee' else 0,
                'has_workout_types': has_workout_types if profile.role == 'employee' else True,
            }
        })
    return JsonResponse(data, safe=False)

@login_required
@user_passes_test(is_admin)
@csrf_exempt
@require_http_methods(["POST"])
def api_invite_user(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'errors': {'__all__': ['Неверный JSON']}}, status=400)

    form_data = {
        'username': data.get('username'),
        'email': data.get('email'),
        'first_name': data.get('first_name'),
        'last_name': data.get('last_name'),
        'patronymic': data.get('patronymic', ''),
        'role': data.get('role'),
        'phone': data.get('phone'),
    }

    form = UserInvitationForm(form_data)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors})

    try:
        raw_password = generate_random_password()
        user = User.objects.create_user(
            username=form.cleaned_data['username'],
            email=form.cleaned_data['email'],
            password=raw_password,
            first_name=form.cleaned_data['first_name'],
            last_name=form.cleaned_data['last_name'],
        )
        profile = user.profile
        profile.role = form.cleaned_data['role']
        profile.phone = form.cleaned_data['phone']
        profile.patronymic = form.cleaned_data['patronymic']
        profile.save()

        # Создаём Employee и назначаем направления
        employee, created = Employee.objects.get_or_create(user_profile=profile)
        workout_type_ids = data.get('workout_types', [])
        if isinstance(workout_type_ids, list):
            workout_types = WorkoutType.objects.filter(id__in=workout_type_ids)
            employee.workout_types.set(workout_types)

        send_user_invitation(user, raw_password)
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Ошибка создания пользователя: {e}")
        return JsonResponse({'success': False, 'errors': {'__all__': [f'Ошибка: {str(e)}']}})
    



@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET"])
def api_get_user_detail(request, user_id):
    try:
        user = User.objects.select_related('profile').get(id=user_id)
        return JsonResponse({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'profile': {
                'role': user.profile.role,
                'phone': user.profile.phone or '',
                'patronymic': user.profile.patronymic or '',
            }
        })
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

@login_required
@user_passes_test(is_admin)
@csrf_exempt
@require_http_methods(["POST"])
def api_update_user(request, user_id):
    logger.info(f"Обновление пользователя {user_id}")
    try:
        user = User.objects.get(id=user_id)
        profile = user.profile
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'errors': {'__all__': ['Пользователь не найден.']}})

    try:
        data = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'errors': {'__all__': ['Неверный формат данных.']}})

    # Валидация
    errors = {}
    fields = ['username', 'email', 'first_name', 'last_name', 'patronymic', 'role', 'phone']
    for field in fields:
        if not data.get(field, '').strip():
            errors[field] = ['Это поле обязательно.']

    if errors:
        return JsonResponse({'success': False, 'errors': errors})

    # Проверка уникальности
    if User.objects.exclude(id=user_id).filter(username=data['username']).exists():
        errors['username'] = ['Пользователь с таким именем уже существует.']
    if User.objects.exclude(id=user_id).filter(email=data['email']).exists():
        errors['email'] = ['Пользователь с таким email уже существует.']

    if errors:
        return JsonResponse({'success': False, 'errors': errors})

    # Сохранение основных данных
    try:
        user.username = data['username']
        user.email = data['email']
        user.first_name = data['first_name']
        user.last_name = data['last_name']
        user.save()

        profile.role = data['role']
        profile.phone = data['phone']
        profile.patronymic = data['patronymic']
        profile.save()

        # ✅ СОХРАНЕНИЕ НАПРАВЛЕНИЙ
        employee, created = Employee.objects.get_or_create(user_profile=profile)
        workout_type_ids = data.get('workout_types', [])
        if isinstance(workout_type_ids, list):
            workout_types = WorkoutType.objects.filter(id__in=workout_type_ids)
            employee.workout_types.set(workout_types)
        # Если workout_types не передано — оставляем как есть (не удаляем!)

        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Ошибка сохранения пользователя {user_id}: {e}")
        return JsonResponse({'success': False, 'errors': {'__all__': [f'Ошибка при сохранении: {str(e)}']}})

@login_required
@user_passes_test(is_admin)
@csrf_exempt
@require_http_methods(["DELETE"])
def api_delete_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        user.delete()
        return JsonResponse({'success': True})
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Пользователь не найден.'}, status=404)

@login_required
@user_passes_test(is_admin)
@csrf_exempt
@require_http_methods(["POST"])
def api_reset_user_password(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        raw_password = generate_random_password()
        user.set_password(raw_password)
        user.save()

        profile = user.profile
        profile.invitation_timestamp = timezone.now()
        profile.save()

        send_user_invitation(user, raw_password)
        return JsonResponse({'success': True, 'message': 'Пароль сброшен и отправлен на email.'})
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Пользователь не найден.'}, status=404)
