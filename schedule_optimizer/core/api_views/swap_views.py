# core/swap_views.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q
from ..models import ShiftAssignment, Employee, ShiftSwapRequest, SwapShift
import json
from ..error_utils import humanize_exception
from ..api_schedule_views import _build_candidate_rows, _slot_to_time_slot

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
        reason = data.get('reason', '').strip()

        if not shift_ids_raw:
            return JsonResponse({'success': False, 'error': 'Не указаны смены'})

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

        from_employee = Employee.objects.get(user_profile=request.user.profile)

        # Создаём заявку
        swap_request = ShiftSwapRequest.objects.create(
            from_employee=from_employee,
            to_employee=None,
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

    except Exception as e:
        return JsonResponse({'success': False, 'error': humanize_exception(e)})


@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET"])
def api_swap_request_candidates(request, swap_id):
    """Кандидаты на замену для заявки. Выбор делает руководитель."""
    try:
        swap = ShiftSwapRequest.objects.select_related(
            'from_employee__user_profile'
        ).prefetch_related(
            'shifts__shift_assignment__workout_type'
        ).get(id=swap_id)

        slot_rows = []
        for swap_shift in swap.shifts.all():
            shift = swap_shift.shift_assignment
            slot_rows.append({
                'date': shift.date,
                'time_slot': _slot_to_time_slot(shift.start_time),
                'workout_type_id': shift.workout_type_id,
                'label': f"{shift.date.strftime('%d.%m.%Y')} {shift.start_time.strftime('%H:%M')}-{shift.end_time.strftime('%H:%M') if shift.end_time else ''}".strip('-'),
            })

        if not slot_rows:
            return JsonResponse({'success': True, 'candidates': [], 'slots_count': 0})

        base_qs = Employee.objects.select_related('user_profile__user').filter(
            user_profile__role='employee',
            user_profile__user__is_active=True,
        ).exclude(user_profile_id=swap.from_employee.user_profile_id)

        results = []
        for employee in base_qs:
            covered = 0
            reasons = []
            for slot in slot_rows:
                rows = _build_candidate_rows(
                    shift_date=slot['date'],
                    time_slot=slot['time_slot'],
                    workout_type_id=slot['workout_type_id'],
                    schedule_id=None,
                    exclude_employee_id=swap.from_employee.user_profile_id,
                    limit=10,
                )
                match = next((r for r in rows if int(r['employee_id']) == int(employee.user_profile_id)), None)
                if match:
                    covered += 1
                    if match.get('reasons'):
                        reasons.append(match['reasons'][0])

            if covered == 0:
                continue

            user = employee.user_profile.user
            full_name = user.get_full_name().strip() or user.username
            results.append({
                'employee_id': employee.id,
                'profile_id': employee.user_profile_id,
                'display_name': full_name,
                'coverage': covered,
                'coverage_pct': round((covered / len(slot_rows)) * 100),
                'sample_reason': reasons[0] if reasons else 'доступен для части слотов',
            })

        results.sort(key=lambda x: (-x['coverage'], x['display_name'].lower()))
        return JsonResponse({
            'success': True,
            'candidates': results,
            'slots_count': len(slot_rows),
        })
    except ShiftSwapRequest.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Заявка не найдена'})
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
    try:
        body = {}
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            body = {}

        swap = ShiftSwapRequest.objects.select_related(
            'from_employee__user_profile',
            'to_employee__user_profile'
        ).prefetch_related(
            'to_employee__workout_types',
            'shifts__shift_assignment__workout_type',
        ).get(id=swap_id)

        selected_employee_id = body.get('to_employee_id')
        if selected_employee_id:
            to_employee = Employee.objects.select_related('user_profile__user').prefetch_related('workout_types').get(id=int(selected_employee_id))
            swap.to_employee = to_employee
        if not swap.to_employee_id:
            return JsonResponse({'success': False, 'error': 'Сначала выберите сотрудника на замену.'})

        manager = request.user
        from_user = swap.from_employee.user_profile.user
        to_user = swap.to_employee.user_profile.user

        logger.info(f"Менеджер {manager.username} утверждает заявку #{swap.id}: "
                    f"{from_user.username} → {to_user.username}")

        # Нельзя менять прошедшие смены.
        today_local = timezone.localdate()
        has_past_shift = any(
            swap_shift.shift_assignment.date < today_local
            for swap_shift in swap.shifts.all()
        )
        if has_past_shift:
            return JsonResponse({
                'success': False,
                'error': 'Нельзя утверждать подмену для смен, дата которых уже прошла.',
            })

        # Нельзя утверждать обмен, если у получателя не выбраны направления.
        to_employee_workout_ids = set(swap.to_employee.workout_types.values_list('id', flat=True))
        if not to_employee_workout_ids:
            return JsonResponse({
                'success': False,
                'error': (
                    f'Нельзя утвердить обмен: у сотрудника "{to_user.username}" не выбраны направления. '
                    'Сначала назначьте направления в профиле сотрудника.'
                ),
            })

        missing_workouts = []
        for swap_shift in swap.shifts.all():
            shift = swap_shift.shift_assignment
            workout = shift.workout_type
            if workout and workout.id not in to_employee_workout_ids:
                missing_workouts.append(workout.name)

        if missing_workouts:
            unique_names = sorted(set(missing_workouts))
            return JsonResponse({
                'success': False,
                'error': (
                    f'Нельзя утвердить обмен: у сотрудника "{to_user.username}" нет нужных направлений '
                    f'для этих занятий ({", ".join(unique_names)}).'
                ),
            })

        # Меняем статус
        swap.status = 'approved_by_manager'
        swap.save(update_fields=['status', 'to_employee'])

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
