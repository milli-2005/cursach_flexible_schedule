"""Утилиты отправки почты с запасным поведением на случай ошибок SMTP."""

import logging

from django.conf import settings
from django.core.mail import get_connection, send_mail


logger = logging.getLogger(__name__)


def send_mail_with_fallback(
    subject: str,
    message: str,
    recipient_list: list[str],
    from_email: str | None = None,
    html_message: str | None = None,
) -> bool:
    """
    Отправляет письмо через текущие настройки почты.
    Если не удалось (например, таймаут SSL/SMTP), пробует запасной режим:
    465 (SSL) <-> 587 (TLS).
    """
    recipients = [email for email in dict.fromkeys(recipient_list or []) if email]
    if not recipients:
        return False

    sender = from_email or settings.DEFAULT_FROM_EMAIL

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=sender,
            recipient_list=recipients,
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as first_exc:
        logger.warning("Primary email send failed, trying fallback SMTP mode: %s", first_exc)

    current_port = int(getattr(settings, "EMAIL_PORT", 587))
    if current_port == 465:
        fallback_port = 587
        use_ssl = False
        use_tls = True
    else:
        fallback_port = 465
        use_ssl = True
        use_tls = False

    try:
        connection = get_connection(
            backend=getattr(settings, "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"),
            host=getattr(settings, "EMAIL_HOST", "smtp.gmail.com"),
            port=fallback_port,
            username=getattr(settings, "EMAIL_HOST_USER", ""),
            password=getattr(settings, "EMAIL_HOST_PASSWORD", ""),
            use_tls=use_tls,
            use_ssl=use_ssl,
            timeout=int(getattr(settings, "EMAIL_TIMEOUT", 25)),
            fail_silently=False,
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=sender,
            recipient_list=recipients,
            html_message=html_message,
            fail_silently=False,
            connection=connection,
        )
        logger.info("Email sent via fallback SMTP mode (port=%s).", fallback_port)
        return True
    except Exception as second_exc:
        logger.exception("Fallback email send failed: %s", second_exc)
        return False

