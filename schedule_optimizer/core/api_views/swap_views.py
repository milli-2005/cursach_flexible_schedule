# core/swap_views.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from ..models import ShiftAssignment, Employee, ShiftSwapRequest
import json

def is_admin(user):
    if not hasattr(user, 'profile'):
        return False
    return user.profile.role == 'manager' or user.is_superuser

@login_required
@require_http_methods(["GET"])
def api_my_shifts_for_swap(request):
    """Возвращает список будущих смен текущего пользователя для обмена."""
    today = timezone.now().date()
    shifts = ShiftAssignment.objects.filter(
        employee__user=request.user,
        date__gte=today,
        status__in=['scheduled', 'confirmed']
    ).select_related('workout_type', 'schedule')

    data = []
    for s in shifts:
        data.append({
            'id': s.id,
            'date': s.date.isoformat(),
            'start_time': s.start_time.strftime('%H:%M'),
            'end_time': s.end_time.strftime('%H:%M') if s.end_time else '',
            'workout': s.workout_type.name if s.workout_type else 'Работа',
        })
    return JsonResponse(data, safe=False)


@login_required
@require_http_methods(["GET"])
def api_employees_for_swap(request):
    """Возвращает список других сотрудников (не текущего пользователя)."""
    employees = Employee.objects.select_related('user_profile__user').exclude(
        user_profile__user=request.user
    )
    data = []
    for emp in employees:
        user = emp.user_profile.user
        name = f"{user.last_name} {user.first_name}"
        if emp.user_profile.patronymic:
            name += f" {emp.user_profile.patronymic}"
        data.append({
            'id': emp.id,
            'name': name
        })
    return JsonResponse(data, safe=False)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_create_swap_request(request):
    try:
        data = json.loads(request.body)
        shift_id = data.get('shift_id')
        to_employee_id = data.get('to_employee_id')  # ← это ID сотрудника (Employee.id)
        reason = data.get('reason', '').strip()

        if not shift_id or not to_employee_id:
            return JsonResponse({'success': False, 'error': 'Не указаны смена или получатель'})

        # === Проверка: смена принадлежит текущему пользователю ===
        # ShiftAssignment.employee ссылается на UserProfile
        shift = ShiftAssignment.objects.get(
            id=shift_id,
            employee=request.user.profile  # ← правильно: UserProfile
        )

        # === Получаем получателя как Employee по ID ===
        to_employee = Employee.objects.get(id=to_employee_id)

        # === Создаём заявку ===
        from_employee = Employee.objects.get(user_profile=request.user.profile)

        ShiftSwapRequest.objects.create(
            from_employee=from_employee,
            to_employee=to_employee,
            shift_assignment=shift,
            reason=reason,
            status='pending'
        )

        return JsonResponse({'success': True, 'message': 'Заявка на обмен отправлена'})

    except ShiftAssignment.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Смена не найдена или не принадлежит вам'})
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Получатель не найден'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})



@login_required
def manager_swap_requests(request):
    if request.user.profile.role != 'manager':
        messages.error(request, "Доступ запрещён.")
        return redirect('dashboard')

    # Все заявки на обмен
    swap_requests = ShiftSwapRequest.objects.select_related(
        'from_employee__user_profile__user',
        'to_employee__user_profile__user',
        'shift_assignment__workout_type'
    ).order_by('-created_at')

    context = {
        'swap_requests': swap_requests,
    }
    return render(request, 'core/swaps/manager_swap_requests.html', context)


#API для одобрения/отклонения
@login_required
@user_passes_test(is_admin)
@csrf_exempt
@require_http_methods(["POST"])
def api_approve_swap_request(request, swap_id):
    try:
        swap = ShiftSwapRequest.objects.get(id=swap_id)
        swap.status = 'approved_by_manager'
        swap.save()
        return JsonResponse({'success': True})
    except ShiftSwapRequest.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Заявка не найдена'})

@login_required
@user_passes_test(is_admin)
@csrf_exempt
@require_http_methods(["POST"])
def api_reject_swap_request(request, swap_id):
    try:
        swap = ShiftSwapRequest.objects.get(id=swap_id)
        swap.status = 'rejected'
        swap.save()
        return JsonResponse({'success': True})
    except ShiftSwapRequest.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Заявка не найдена'})