# core/api_workout_views.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from .models import WorkoutType

def is_manager(user):
    """Проверяет, является ли пользователь руководителем."""
    if not hasattr(user, 'profile'):
        return False
    return user.profile.role == 'manager'

@login_required
@user_passes_test(is_manager)
@require_http_methods(["GET"])
def api_get_workout_types(request):
    """Получить список всех типов занятий."""
    workout_types = WorkoutType.objects.all()
    data = [
        {
            'id': wt.id,
            'name': wt.name,
            'description': wt.description,
        }
        for wt in workout_types
    ]
    return JsonResponse(data, safe=False)

@login_required
@user_passes_test(is_manager)
@csrf_exempt
@require_http_methods(["POST"])
def api_create_workout_type(request):
    """Создать новый тип занятия."""
    try:
        data = json.loads(request.body.decode('utf-8'))
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()

        if not name:
            return JsonResponse({'success': False, 'errors': {'name': ['Название обязательно.']}})

        workout_type = WorkoutType.objects.create(name=name, description=description)
        return JsonResponse({
            'success': True,
            'workout_type': {
                'id': workout_type.id,
                'name': workout_type.name,
                'description': workout_type.description,
            }
        })

    except Exception as e:
        return JsonResponse({'success': False, 'errors': {'__all__': [str(e)]}})

@login_required
@user_passes_test(is_manager)
@csrf_exempt
@require_http_methods(["PUT"])
def api_update_workout_type(request, workout_type_id):
    """Обновить существующий тип занятия."""
    try:
        workout_type = WorkoutType.objects.get(id=workout_type_id)
        data = json.loads(request.body.decode('utf-8'))
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()

        if not name:
            return JsonResponse({'success': False, 'errors': {'name': ['Название обязательно.']}})

        workout_type.name = name
        workout_type.description = description
        workout_type.save()

        return JsonResponse({
            'success': True,
            'workout_type': {
                'id': workout_type.id,
                'name': workout_type.name,
                'description': workout_type.description,
            }
        })

    except WorkoutType.DoesNotExist:
        return JsonResponse({'success': False, 'errors': {'__all__': ['Тип занятия не найден.']}})
    except Exception as e:
        return JsonResponse({'success': False, 'errors': {'__all__': [str(e)]}})

@login_required
@user_passes_test(is_manager)
@csrf_exempt
@require_http_methods(["DELETE"])
def api_delete_workout_type(request, workout_type_id):
    """Удалить тип занятия."""
    try:
        workout_type = WorkoutType.objects.get(id=workout_type_id)
        workout_type.delete()
        return JsonResponse({'success': True})
    except WorkoutType.DoesNotExist:
        return JsonResponse({'success': False, 'errors': {'__all__': ['Тип занятия не найден.']}})