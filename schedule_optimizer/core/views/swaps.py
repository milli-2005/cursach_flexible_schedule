"""Страницы обмена сменами между сотрудниками."""

from .auth import *

@login_required
def shift_swaps(request):
    """Показывает сотруднику его заявки на обмен сменами и выбранные смены для обмена."""
    if request.user.profile.role != 'employee':
        return redirect('dashboard')

    shift_ids_str = request.GET.get('shift_ids')
    selected_shifts = []

    if shift_ids_str:
        try:
            shift_ids = [int(x) for x in shift_ids_str.split(',')]
            selected_shifts = ShiftAssignment.objects.filter(
                id__in=shift_ids,
                employee=request.user.profile
            )
        except ValueError:
            pass

    # Всегда загружаем список своих заявок
    my_requests = ShiftSwapRequest.objects.filter(
        from_employee__user_profile=request.user.profile
    ).select_related(
        'to_employee__user_profile__user'
    ).prefetch_related('shifts__shift_assignment').order_by('-created_at')

    context = {
        'selected_shifts': selected_shifts,
        'my_requests': my_requests,
    }

    if selected_shifts:
        context['shift_ids_json'] = json.dumps([s.id for s in selected_shifts])

    return render(request, 'core/swaps/shift_swaps.html', context)


@login_required
@user_passes_test(lambda u: u.profile.role in ['manager', 'studio_admin'])
def manager_swap_requests(request):
    """Страница для менеджера: просмотр и одобрение всех заявок"""
    swap_requests = ShiftSwapRequest.objects.select_related(
    'from_employee__user_profile__user',
    'to_employee__user_profile__user'
).prefetch_related(
    'shifts__shift_assignment'
).order_by('-created_at')

    context = {
        'swap_requests': swap_requests,
    }
    return render(request, 'core/swaps/manager_swap_requests.html', context)
