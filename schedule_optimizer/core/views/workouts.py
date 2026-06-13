"""Страница управления типами занятий и направлениями студии."""

from .auth import *


@login_required
def workout_types(request):
    """
    Страница управления типами занятий.
    Доступна только руководителю.
    """
    return render(request, 'core/workouts/workout_types.html')
