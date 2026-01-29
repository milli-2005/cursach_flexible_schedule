# core/management/commands/fill_schedules_with_realistic_shifts.py
from django.core.management.base import BaseCommand
from core.models import Schedule, ShiftAssignment, UserProfile, Availability, WorkoutType
from datetime import timedelta

class Command(BaseCommand):
    help = 'Заполняет графики сменами на основе реальной или имитированной доступности'

    def handle(self, *args, **options):
        employees = UserProfile.objects.filter(role='employee')
        if not employees.exists():
            self.stdout.write(self.style.ERROR('Нет сотрудников'))
            return

        # Получаем хотя бы один тип занятия
        workout_types = WorkoutType.objects.all()
        if not workout_types.exists():
            workout_type = WorkoutType.objects.create(name="Групповая тренировка")
        else:
            workout_type = workout_types.first()

        schedules = Schedule.objects.filter(status='approved')
        if not schedules.exists():
            self.stdout.write(self.style.WARNING('Нет утверждённых графиков'))
            return

        total_created = 0

        for schedule in schedules:
            self.stdout.write(f"Заполняем график: {schedule.name}")
            current_date = schedule.start_date

            while current_date <= schedule.end_date:
                weekday = current_date.weekday()  # 0=Пн, ..., 6=Вс

                for emp in employees:
                    # === ИМИТАЦИЯ ДОСТУПНОСТИ ===
                    # Можно заменить на реальный запрос к Availability, если данные есть
                    available_slots = []

                    # Пример логики: каждый сотрудник работает 3 дня в неделю
                    if emp.id % 3 == 0:
                        # Сотрудник 1: Пн, Ср, Пт
                        if weekday in [0, 2, 4]:
                            available_slots = [("09:00", "10:00"), ("11:00", "12:00")]
                    elif emp.id % 3 == 1:
                        # Сотрудник 2: Вт, Чт, Сб
                        if weekday in [1, 3, 5]:
                            available_slots = [("14:00", "15:00"), ("16:00", "17:00")]
                    else:
                        # Сотрудник 3: Пн-Пт утро
                        if weekday in [0, 1, 2, 3, 4]:
                            available_slots = [("08:00", "09:00")]

                    # Создаём смены на основе доступности
                    for start_time, end_time in available_slots:
                        obj, created = ShiftAssignment.objects.get_or_create(
                            schedule=schedule,
                            employee=emp,
                            date=current_date,
                            start_time=start_time,
                            defaults={
                                'end_time': end_time,
                                'workout_type': workout_type
                            }
                        )
                        if created:
                            total_created += 1

                current_date += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f'Добавлено {total_created} смен на основе логики доступности'))