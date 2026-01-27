# core/tasks.py

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from .models import Schedule, UserProfile

# === ЗАДАЧА 1: Напоминание о доступности (во вторник) ===
@shared_task
def send_availability_reminder():
    draft_schedules = Schedule.objects.filter(status='draft')
    if not draft_schedules.exists():
        return

    employees = UserProfile.objects.filter(role='employee')
    employee_emails = [emp.user.email for emp in employees if emp.user.email]

    if not employee_emails:
        return

    for schedule in draft_schedules:
        deadline_day = dict(Schedule.AVAILABILITY_DEADLINE_CHOICES)[schedule.availability_deadline_weekday]
        message = f"Напоминаем: укажите вашу доступность для графика '{schedule.name}' до {deadline_day}!"

        send_mail(
            subject="Напоминание: укажите доступность",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=employee_emails,
            fail_silently=False,
        )

# === ЗАДАЧА 2: Автоматическое утверждение графика (каждые 10 мин) ===
@shared_task
def auto_approve_schedules():
    one_hour_ago = timezone.now() - timedelta(hours=1)
    pending_schedules = Schedule.objects.filter(
        status='pending',
        created_at__lte=one_hour_ago
    )

    for schedule in pending_schedules:
        total = UserProfile.objects.filter(role='employee').count()
        responded = schedule.approvals.filter(approved__isnull=False).count()

        if responded == total:
            # Все ответили — утверждаем
            schedule.status = 'approved'
            schedule.save()
        else:
            # Не все ответили — считаем как подтверждение
            for approval in schedule.approvals.filter(approved__isnull=True):
                approval.approved = True
                approval.responded_at = timezone.now()
                approval.save()
            schedule.status = 'approved'
            schedule.save()