# core/management/commands/create_admin.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserProfile

class Command(BaseCommand):
    help = 'Создает суперпользователя с профилем администратора'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Имя пользователя')
        parser.add_argument('email', type=str, help='Email')
        parser.add_argument('password', type=str, help='Пароль')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']

        user = User.objects.create_superuser(username, email, password)
        profile = UserProfile.objects.get_or_create(user=user)[0] # get_or_create, если сигналы работают, но на всякий случай
        profile.role = 'admin' # Или другая роль по умолчанию для суперпользователей
        profile.current_role = 'admin'
        profile.save()

        self.stdout.write(
            self.style.SUCCESS(f'Суперпользователь {username} успешно создан с профилем администратора.')
        )