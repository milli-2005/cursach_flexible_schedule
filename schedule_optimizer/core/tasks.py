# core/tasks.py

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from .models import Schedule, UserProfile


# === ЗАДАЧА 1: Напоминание о доступности  ===
@shared_task
def send_availability_reminder():
    # Получаем глобальные настройки
    try:
        settings_obj = GlobalSettings.objects.get(pk=1)
    except GlobalSettings.DoesNotExist:
        return

    today_weekday = timezone.now().weekday()
    deadline_weekday = settings_obj.availability_deadline_weekday
    reminder_day = (deadline_weekday - 1) % 7

    if today_weekday != reminder_day:
        return

    # Отправляем напоминание ВСЕМ сотрудникам
    employees = UserProfile.objects.filter(role='employee')
    emails = [emp.user.email for emp in employees if emp.user.email]

    if not emails:
        return

    deadline_label = dict(GlobalSettings.AVAILABILITY_DEADLINE_CHOICES)[deadline_weekday]
    message = f"Напоминаем: завтра последний день для указания вашей доступности!\n\nДедлайн: {deadline_label}."

    send_mail(
        subject="Напоминание: укажите доступность",
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=emails,
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