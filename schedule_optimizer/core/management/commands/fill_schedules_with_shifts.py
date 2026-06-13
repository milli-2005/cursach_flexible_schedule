"""Команда Django для заполнения существующих графиков сменами."""

# core/management/commands/fill_schedules_with_realistic_shifts.py
from django.core.management.base import BaseCommand
from core.models import Schedule, ShiftAssignment, UserProfile, WorkoutType
from datetime import timedelta, time

class Command(BaseCommand):
    """Команда manage.py, выполняющая служебное действие проекта."""
    help = 'Заполняет утверждённые графики реалистичными сменами (50 минут, кратные 10 минутам)'

    def handle(self, *args, **options):
        """Выполняет вспомогательное действие внутри своей части проекта."""
        employees = UserProfile.objects.filter(role='employee')
        if not employees.exists():
            self.stdout.write(self.style.ERROR('Нет сотрудников'))
            return

        workout_types = WorkoutType.objects.all()
        if not workout_types.exists():
            workout_type = WorkoutType.objects.create(name="Групповая тренировка")
            workout_types = [workout_type]
        else:
            workout_types = list(workout_types)

        schedules = Schedule.objects.filter(status='approved')
        if not schedules.exists():
            self.stdout.write(self.style.WARNING('Нет утверждённых графиков'))
            return

        total_created = 0

        # Слоты: начало в :00/:10/... длительностью 50 мин
        SLOT_TIMES = [
            ("08:00", "08:50"),
            ("09:00", "09:50"),
            ("10:00", "10:50"),
            ("11:00", "11:50"),
            ("12:00", "12:50"),
            ("13:00", "13:50"),
            ("14:00", "14:50"),
            ("15:00", "15:50"),
            ("16:00", "16:50"),
            ("17:00", "17:50"),
            ("18:00", "18:50"),
            ("19:00", "19:50"),
            ("20:00", "20:50"),
        ]

        for schedule in schedules:
            self.stdout.write(f"Заполняем график: {schedule.name} ({schedule.start_date} – {schedule.end_date})")
            current_date = schedule.start_date

            while current_date <= schedule.end_date:
                weekday = current_date.weekday()  # 0=Пн, ..., 6=Вс

                for emp in employees:
                    # === Пример логики: каждый работает 3 дня в неделю ===
                    slots_to_assign = []

                    if emp.id % 3 == 0:
                        # Пн, Ср, Пт → утро
                        if weekday in [0, 2, 4]:
                            slots_to_assign = [("09:00", "09:50"), ("11:00", "11:50")]
                    elif emp.id % 3 == 1:
                        # Вт, Чт, Сб → день
                        if weekday in [1, 3, 5]:
                            slots_to_assign = [("14:00", "14:50"), ("16:00", "16:50")]
                    else:
                        # Остальные — Пн-Пт вечером
                        if weekday in [0, 1, 2, 3, 4]:
                            slots_to_assign = [("18:00", "18:50"), ("19:00", "19:50")]

                    # Выбираем тип занятия поочерёдно
                    wt_index = (emp.id + current_date.day) % len(workout_types)
                    workout_type = workout_types[wt_index]

                    for start_str, end_str in slots_to_assign:
                        obj, created = ShiftAssignment.objects.get_or_create(
                            schedule=schedule,
                            employee=emp,
                            date=current_date,
                            start_time=time.fromisoformat(start_str),
                            defaults={
                                'end_time': time.fromisoformat(end_str),
                                'workout_type': workout_type,
                                'status': 'scheduled'
                            }
                        )
                        if created:
                            total_created += 1

                current_date += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f'✅ Успешно добавлено {total_created} смен'))