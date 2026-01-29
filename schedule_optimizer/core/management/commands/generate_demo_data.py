# core/management/commands/generate_demo_data.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta, date
from core.models import Schedule, ShiftAssignment, UserProfile, WorkoutType
import random


class Command(BaseCommand):
    help = 'Генерирует демо-данные для отчётов: графики и назначения за последние 4 недели'

    def handle(self, *args, **options):
        # Получаем всех сотрудников и типы занятий
        employees = UserProfile.objects.filter(role='employee')
        workout_types = WorkoutType.objects.all()

        if not employees.exists():
            self.stdout.write(self.style.ERROR('Нет сотрудников с ролью "employee"'))
            return

        if not workout_types.exists():
            # Создаём базовые типы, если нет
            workout_types = [
                WorkoutType.objects.get_or_create(name="Групповая тренировка")[0],
                WorkoutType.objects.get_or_create(name="Персональная тренировка")[0],
                WorkoutType.objects.get_or_create(name="Йога")[0],
            ]

        today = timezone.now().date()

        # Генерируем графики за последние 4 недели
        for week_offset in range(1, 5):  # 1, 2, 3, 4 недели назад
            start_date = today - timedelta(weeks=week_offset) - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)

            # Создаём график
            schedule_name = f"Демо-график за {start_date.strftime('%d.%m')}–{end_date.strftime('%d.%m.%Y')}"
            schedule, created = Schedule.objects.get_or_create(
                name=schedule_name,
                start_date=start_date,
                end_date=end_date,
                defaults={'status': 'approved'}
            )

            if created:
                self.stdout.write(f"Создан график: {schedule_name}")

            # Создаём назначения для каждого дня и каждого сотрудника
            for emp in employees:
                for day_offset in range(7):  # Пн–Вс
                    work_date = start_date + timedelta(days=day_offset)

                    # Случайное количество смен в день (0–2)
                    num_shifts = random.randint(0, 2)

                    for _ in range(num_shifts):
                        # Случайное время: с 9 до 20 часов
                        hour = random.randint(9, 19)
                        start_time = f"{hour:02d}:00"
                        end_time = f"{hour + 1:02d}:00"

                        # Случайный тип занятия
                        workout_type = random.choice(workout_types)

                        # Создаём назначение
                        ShiftAssignment.objects.get_or_create(
                            employee=emp,
                            date=work_date,
                            start_time=start_time,
                            end_time=end_time,
                            workout_type=workout_type,
                            schedule=schedule
                        )

        self.stdout.write(self.style.SUCCESS('Демо-данные успешно созданы!'))