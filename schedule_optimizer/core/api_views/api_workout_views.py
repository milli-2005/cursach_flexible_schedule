
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from ..models import WorkoutType, UserProfile, Employee

def is_manager(user):
    """Проверка: пользователь — руководитель"""
    if not hasattr(user, 'profile'):
        return False
    return user.profile.role == 'manager'

@login_required
@user_passes_test(is_manager)
@require_http_methods(["GET"])
def api_get_workout_types(request):
    """Получить список всех типов занятий (для модалок)"""
    types = WorkoutType.objects.all().values('id', 'name', 'description')
    return JsonResponse(list(types), safe=False)


@login_required
@user_passes_test(is_manager)
@csrf_exempt
@require_http_methods(["POST"])
def api_create_workout_type(request):
    """Создать новый тип занятия"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()

        if not name:
            return JsonResponse({'success': False, 'errors': {'name': ['Название обязательно.']}})

        wt = WorkoutType.objects.create(name=name, description=description)
        return JsonResponse({
            'success': True,
            'workout_type': {
                'id': wt.id,
                'name': wt.name,
                'description': wt.description
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'errors': {'__all__': [str(e)]}})


@login_required
@user_passes_test(is_manager)
@csrf_exempt
@require_http_methods(["PUT"])
def api_update_workout_type(request, workout_type_id):
    """Обновить тип занятия"""
    try:
        wt = WorkoutType.objects.get(id=workout_type_id)
        data = json.loads(request.body.decode('utf-8'))
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()

        if not name:
            return JsonResponse({'success': False, 'errors': {'name': ['Название обязательно.']}})

        wt.name = name
        wt.description = description
        wt.save()

        return JsonResponse({
            'success': True,
            'workout_type': {
                'id': wt.id,
                'name': wt.name,
                'description': wt.description
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
    """Удалить тип занятия"""
    try:
        wt = WorkoutType.objects.get(id=workout_type_id)
        wt.delete()
        return JsonResponse({'success': True})
    except WorkoutType.DoesNotExist:
        return JsonResponse({'success': False, 'errors': {'__all__': ['Тип занятия не найден.']}})
    



@login_required
@user_passes_test(is_manager)
@require_http_methods(["GET"])
def api_get_employee_workout_types(request, user_id):
    """
    Получить список ID направлений, назначенных сотруднику (по user_id).
    Используется при редактировании пользователя.
    """
    try:
        profile = UserProfile.objects.get(user_id=user_id)
        employee = Employee.objects.get(user_profile=profile)
        # Возвращаем только ID — для JS-галочек
        workout_type_ids = list(employee.workout_types.values_list('id', flat=True))
        return JsonResponse(workout_type_ids, safe=False)
    except (UserProfile.DoesNotExist, Employee.DoesNotExist):
        return JsonResponse([], safe=False)