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
            Если пользователь просто сохранен, проверяем, является ли он суперпользователем,
            и если да, и у него нет профиля с ролью admin, устанавливаем её.
            """
            if created:
                # Создаем профиль при создании пользователя
                profile = UserProfile.objects.create(user=instance)
                # Если это суперпользователь, сразу устанавливаем роль администратора
                if instance.is_superuser:
                    profile.role = 'admin'
                    profile.current_role = 'admin'
                    profile.save()
            else:
                # При обновлении пользователя проверяем, не стал ли он суперпользователем
                # и существует ли уже профиль
                if instance.is_superuser:
                    profile, created = UserProfile.objects.get_or_create(user=instance)
                    if profile.role != 'admin':
                        profile.role = 'admin'
                        profile.current_role = 'admin'
                        profile.save()

        # Подключаем сигнал при готовности приложения
        post_save.connect(create_or_update_user_profile, sender=User)
