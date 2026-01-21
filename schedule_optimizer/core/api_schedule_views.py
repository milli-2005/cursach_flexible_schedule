# core/api_schedule_views.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.dateparse import parse_date
import json
from .models import Schedule, ShiftAssignment, UserProfile, WorkoutType


def is_manager(user):
    if not hasattr(user, 'profile'):
        return False
    return user.profile.role == 'manager'


@login_required
@user_passes_test(is_manager)
@csrf_exempt
@require_http_methods(["POST"])
def api_save_schedule(request):
    try:
        data = json.loads(request.body.decode('utf-8'))

        # Создаем график
        schedule = Schedule.objects.create(
            name=data['name'],
            start_date=parse_date(data['start_date']),
            end_date=parse_date(data['end_date']),
            created_by=request.user
        )

        # Сохраняем назначения
        for assignment_data in data['assignments']:
            employee = UserProfile.objects.get(id=assignment_data['employee_id'])
            workout_type = None
            if assignment_data.get('workout_type_id'):
                workout_type = WorkoutType.objects.get(id=assignment_data['workout_type_id'])

            start_time_str, end_time_str = assignment_data['time_slot'].split('–')

            ShiftAssignment.objects.create(
                schedule=schedule,
                employee=employee,
                workout_type=workout_type,
                date=parse_date(assignment_data['date']),
                start_time=start_time_str,
                end_time=end_time_str
            )

        return JsonResponse({'success': True, 'schedule_id': schedule.id})

    except Exception as e:
        # ВСЕГДА возвращаем JSON, даже при ошибке!
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@user_passes_test(is_manager)
@csrf_exempt
@require_http_methods(["PUT"])
def api_update_schedule(request, schedule_id):
    try:
        schedule = Schedule.objects.get(id=schedule_id)
        data = json.loads(request.body.decode('utf-8'))

        # 1. Удаляем все старые назначения
        ShiftAssignment.objects.filter(schedule=schedule).delete()

        # 2. Создаем новые назначения
        for assignment_data in data['assignments']:
            employee_id = assignment_data['employee_id']
            workout_type_id = assignment_data.get('workout_type_id')
            date_str = assignment_data['date']
            time_slot = assignment_data['time_slot']

            start_time_str, end_time_str = time_slot.split('–')
            employee = UserProfile.objects.get(id=employee_id)
            workout_type = WorkoutType.objects.get(id=workout_type_id) if workout_type_id else None

            ShiftAssignment.objects.create(
                schedule=schedule,
                employee=employee,
                workout_type=workout_type,
                date=parse_date(date_str),
                start_time=start_time_str,
                end_time=end_time_str
            )

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})