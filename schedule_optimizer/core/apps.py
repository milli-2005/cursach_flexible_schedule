# core/apps.py
from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Импорты внутри ready()
        from django.db.models.signals import post_save
        from django.contrib.auth.models import User
        from .models import UserProfile # Импортируем UserProfile из текущего приложения

        def create_or_update_user_profile(sender, instance, created, **kwargs):
            """
            Сигнал, который срабатывает при сохранении User.
            Если пользователь был создан (created=True), создаем ему профиль.
            Если это суперпользователь и он был создан, устанавливаем ему роль admin.
            """
            if created:
                # Создаем профиль при создании пользователя
                profile = UserProfile.objects.create(user=instance)

                if instance.is_superuser:
                    profile.role = 'manager'
                    profile.save()

        # Подключаем сигнал при готовности приложения
        post_save.connect(create_or_update_user_profile, sender=User)
