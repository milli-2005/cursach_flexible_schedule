# core/swap_views.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from ..models import ShiftAssignment, Employee, ShiftSwapRequest, SwapShift
import json
from ..error_utils import humanize_exception

import logging

logger = logging.getLogger(__name__)


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
        shift_ids_raw = data.get('shift_ids')
        to_employee_id = data.get('to_employee_id')
        reason = data.get('reason', '').strip()

        if not shift_ids_raw or not to_employee_id:
            return JsonResponse({'success': False, 'error': 'Не указаны смены или получатель'})

        # Поддерживаем и строку, и список
        if isinstance(shift_ids_raw, str):
            try:
                shift_ids = json.loads(shift_ids_raw)
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'error': 'Неверный формат shift_ids'})
        elif isinstance(shift_ids_raw, list):
            shift_ids = shift_ids_raw
        else:
            return JsonResponse({'success': False, 'error': 'shift_ids должен быть списком или JSON-строкой'})

        if not isinstance(shift_ids, list):
            return JsonResponse({'success': False, 'error': 'shift_ids должен быть списком'})

        # Проверяем, что все смены принадлежат текущему пользователю
        shifts = ShiftAssignment.objects.filter(
            id__in=shift_ids,
            employee=request.user.profile
        )
        if len(shifts) != len(shift_ids):
            return JsonResponse({'success': False, 'error': 'Некоторые смены не найдены или не принадлежат вам'})

        to_employee = Employee.objects.get(id=to_employee_id)
        from_employee = Employee.objects.get(user_profile=request.user.profile)

        # Создаём заявку
        swap_request = ShiftSwapRequest.objects.create(
            from_employee=from_employee,
            to_employee=to_employee,
            reason=reason,
            status='pending'
        )

        # Добавляем смены
        for shift in shifts:
            SwapShift.objects.create(
                swap_request=swap_request,
                shift_assignment=shift
            )

        return JsonResponse({'success': True, 'message': 'Заявка на обмен отправлена'})

    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Получатель не найден'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': humanize_exception(e)})


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
    print("🔥 ФУНКЦИЯ ВЫЗВАНА")
    try:
        swap = ShiftSwapRequest.objects.select_related(
            'from_employee__user_profile',
            'to_employee__user_profile'
        ).prefetch_related('shifts__shift_assignment').get(id=swap_id)

        manager = request.user
        from_user = swap.from_employee.user_profile.user
        to_user = swap.to_employee.user_profile.user

        logger.info(f"Менеджер {manager.username} утверждает заявку #{swap.id}: "
                    f"{from_user.username} → {to_user.username}")

        # Меняем статус
        swap.status = 'approved_by_manager'
        swap.save()

        # Меняем владельца для всех смен
        updated_shifts = []
        for swap_shift in swap.shifts.all():
            shift = swap_shift.shift_assignment
            old_owner = shift.employee.user.username if shift.employee else 'None'
            shift.employee = swap.to_employee.user_profile
            shift.save()
            updated_shifts.append(f"{shift.date} {shift.start_time}")

        logger.info(f"Обновлены смены в заявке #{swap.id}: {', '.join(updated_shifts)}")

        return JsonResponse({'success': True})

    except ShiftSwapRequest.DoesNotExist:
        error_msg = f"Заявка #{swap_id} не найдена при попытке утверждения"
        logger.error(error_msg)
        return JsonResponse({'success': False, 'error': 'Заявка не найдена'})
    except Exception as e:
        error_msg = f"Ошибка при утверждении заявки #{swap_id}: {str(e)}"
        logger.error(error_msg)
        return JsonResponse({'success': False, 'error': humanize_exception(e)})




@login_required
@user_passes_test(is_admin)
@csrf_exempt
@require_http_methods(["POST"])
def api_reject_swap_request(request, swap_id):
    try:
        swap = ShiftSwapRequest.objects.get(id=swap_id)
        manager = request.user
        from_user = swap.from_employee.user_profile.user
        to_user = swap.to_employee.user_profile.user

        logger.info(f"Менеджер {manager.username} отклоняет заявку #{swap.id}: "
                    f"{from_user.username} → {to_user.username}")

        swap.status = 'rejected'
        swap.save()

        logger.info(f"Заявка #{swap.id} отклонена")

        return JsonResponse({'success': True})

    except ShiftSwapRequest.DoesNotExist:
        error_msg = f"Заявка #{swap_id} не найдена при попытке отклонения"
        logger.error(error_msg)
        return JsonResponse({'success': False, 'error': 'Заявка не найдена'})
    except Exception as e:
        error_msg = f"Ошибка при отклонении заявки #{swap_id}: {str(e)}"
        logger.error(error_msg)
        return JsonResponse({'success': False, 'error': humanize_exception(e)})
