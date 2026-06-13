"""Контекстные процессоры добавляют глобальные уведомления в шаблоны без ручной передачи в каждом view."""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from .models import ScheduleApproval


def _next_week_bounds(today):
    """Вычисляет даты начала и конца следующей недели для уведомлений сотрудника."""
    days_to_next_monday = (7 - today.weekday()) % 7
    if days_to_next_monday == 0:
        days_to_next_monday = 7
    next_week_start = today + timedelta(days=days_to_next_monday)
    next_week_end = next_week_start + timedelta(days=6)
    return next_week_start, next_week_end


def pending_schedule_approval_notice(request):
    """Добавляет в шаблоны уведомление о графиках, которые сотрудник еще не подтвердил."""
    if not request.user.is_authenticated:
        return {}

    profile = getattr(request.user, "profile", None)
    if not profile or profile.role != "employee":
        return {}

    today = timezone.localdate()
    next_week_start, next_week_end = _next_week_bounds(today)

    pending_qs = (
        ScheduleApproval.objects.filter(
            employee=profile,
            approved__isnull=True,
            schedule__status="pending",
            schedule__start_date__lte=next_week_end,
            schedule__end_date__gte=next_week_start,
        )
        .select_related("schedule")
        .order_by("schedule__start_date", "schedule__id")
    )

    first = pending_qs.first()
    return {
        "pending_next_week_approvals_count": pending_qs.count(),
        "pending_next_week_approvals": pending_qs[:5],
        "pending_next_week_first_schedule_url": (
            reverse("schedule_detail", args=[first.schedule_id]) if first else ""
        ),
    }


def manager_schedule_feedback_notice(request):
    """Добавляет руководителю уведомление об актуальных ответах сотрудников по графикам."""
    if not request.user.is_authenticated:
        return {}

    profile = getattr(request.user, "profile", None)
    if not profile or profile.role not in {"manager", "studio_admin"}:
        return {}

    today = timezone.localdate()

    approvals_qs = (
        ScheduleApproval.objects.filter(
            schedule__status="pending",
            responded_at__isnull=False,
            schedule__end_date__gte=today,
            approved__isnull=False,
        )
        .select_related("schedule", "employee__user")
        .order_by("-responded_at")
    )

    rejected_qs = approvals_qs.filter(approved=False)
    approved_qs = approvals_qs.filter(approved=True)

    target = rejected_qs.first() or approvals_qs.first()
    target_url = reverse("schedule_detail", args=[target.schedule_id]) if target else ""

    latest_items = []
    for row in approvals_qs[:5]:
        latest_items.append({
            "employee_name": row.employee.user.get_full_name() or row.employee.user.username,
            "schedule_name": row.schedule.name,
            "approved": bool(row.approved),
        })

    return {
        "manager_feedback_rejected_count": rejected_qs.count(),
        "manager_feedback_approved_count": approved_qs.count(),
        "manager_feedback_total_count": approvals_qs.count(),
        "manager_feedback_latest_items": latest_items,
        "manager_feedback_target_url": target_url,
    }
