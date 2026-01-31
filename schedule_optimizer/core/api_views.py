# core/api_views.py
import logging
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import UserProfile
from .forms import UserInvitationForm
import json
import secrets
import string
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

def is_admin(user):
    if not hasattr(user, 'profile'):
        return False
    return user.profile.role == 'manager' or user.is_superuser

def generate_random_password(length=12):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password

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

    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )

@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET"])
def api_get_users(request):
    users = User.objects.select_related('profile').all()
    users_data = []
    for user in users:
        users_data.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'profile': {
                'role': user.profile.role,
                'role_display': user.profile.get_role_display(),
                'position': user.profile.position,
                'phone': user.profile.phone,
            }
        })
    return JsonResponse(users_data, safe=False)

@login_required
@user_passes_test(is_admin)
@csrf_exempt
@require_http_methods(["POST"])
def api_invite_user(request):
    form = UserInvitationForm(request.POST)
    if form.is_valid():
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
            profile.position = form.cleaned_data['position']
            profile.phone = form.cleaned_data['phone']  # уже нормализован
            profile.invitation_timestamp = timezone.now()
            profile.save()

            try:
                send_user_invitation(user, raw_password)
            except Exception as e:
                import logging
                logging.error(f'Ошибка отправки email для {user.username}: {str(e)}')

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'errors': {'__all__': [f'Ошибка создания: {str(e)}']}})
    else:
        return JsonResponse({'success': False, 'errors': form.errors})



@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET"])
def api_get_user_detail(request, user_id):
    try:
        user = User.objects.select_related('profile').get(id=user_id)
        user_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'profile': {
                'role': user.profile.role,
                'position': user.profile.position,
                'phone': user.profile.phone,
            }
        }
        return JsonResponse(user_data)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)


@login_required
@user_passes_test(is_admin)
@csrf_exempt
@require_http_methods(["POST"])
def api_update_user(request, user_id):
    logger.info(f"Received POST request to update user {user_id}")
    try:
        user = User.objects.get(id=user_id)
        profile = user.profile
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for update")
        return JsonResponse({'success': False, 'errors': {'__all__': ['Пользователь не найден.']}})

    try:
        data = json.loads(request.body.decode('utf-8'))
        logger.info(f"Received JSON data for update: {data}")
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return JsonResponse({'success': False, 'errors': {'__all__': ['Неверный формат данных.']}})

    # Получаем и очищаем все поля
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    role = data.get('role', '').strip()
    position = data.get('position', '').strip()
    phone = data.get('phone', '').strip()

    errors = {}

    # === ОБЯЗАТЕЛЬНЫЕ ПОЛЯ ===

    if not username:
        errors['username'] = ['Это поле обязательно.']
    elif User.objects.exclude(id=user_id).filter(username=username).exists():
        errors['username'] = ['Пользователь с таким именем уже существует.']

    if not email:
        errors['email'] = ['Это поле обязательно.']
    elif User.objects.exclude(id=user_id).filter(email=email).exists():
        errors['email'] = ['Пользователь с таким email уже существует.']

    if not first_name:
        errors['first_name'] = ['Имя обязательно.']

    if not last_name:
        errors['last_name'] = ['Фамилия обязательна.']

    if not role:
        errors['role'] = ['Роль обязательна.']
    elif role not in dict(UserProfile.ROLE_CHOICES):
        errors['role'] = ['Выбрана недопустимая роль.']

    if not position:
        errors['position'] = ['Должность обязательна.']
    elif position not in dict(UserProfile.POSITION_CHOICES):
        errors['position'] = ['Выбрана недопустимая должность.']

    if not phone:
        errors['phone'] = ['Телефон обязателен.']
    else:
        # Опциональная проверка формата (можно убрать, если не нужна)
        import re
        if not re.match(r'^[\+]?[0-9\s\-\(\)]{7,}$', phone):
            errors['phone'] = ['Неверный формат телефона. Пример: +7 999 123-45-67']

    # === Если есть ошибки ===
    if errors:
        logger.warning(f"Validation errors for user {user_id}: {errors}")
        return JsonResponse({'success': False, 'errors': errors})

    # === Сохранение ===
    try:
        # User
        user.username = username
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.save()

        # Profile
        profile.role = role
        profile.position = position
        profile.phone = phone
        profile.save()

        logger.info(f"User {user_id} updated successfully")
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Error saving user {user_id}: {str(e)}")
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

        # Обновляем профиль и отправляем письмо
        profile = user.profile
        profile.invitation_timestamp = timezone.now() # Устанавливаем временную метку сброса
        profile.save()

        try:
            send_user_invitation(user, raw_password)
            return JsonResponse({'success': True, 'message': 'Пароль сброшен и отправлен на email.'})
        except Exception as e:
            import logging
            logging.error(f'Ошибка отправки email при сбросе пароля для {user.username}: {str(e)}')
            # Возвращаем успех, но с предупреждением
            return JsonResponse({'success': True, 'message': 'Пароль сброшен, но email не отправлен. См. логи.'})

    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Пользователь не найден.'}, status=404)