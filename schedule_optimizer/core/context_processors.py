from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from .models import ScheduleApproval


def _next_week_bounds(today):
    days_to_next_monday = (7 - today.weekday()) % 7
    if days_to_next_monday == 0:
        days_to_next_monday = 7
    next_week_start = today + timedelta(days=days_to_next_monday)
    next_week_end = next_week_start + timedelta(days=6)
    return next_week_start, next_week_end


def pending_schedule_approval_notice(request):
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

