"""Create 2 trainer users with full profiles, permanent passwords, and history."""
import random
from datetime import date, time, datetime, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    UserProfile, Employee, WorkoutType, Schedule, ShiftAssignment,
    ScheduleApproval, ScheduleVersion, ScheduleVersionAssignment, Availability,
)


class Command(BaseCommand):
    help = 'Создаёт 2 тренеров с полноценными профилями и историей работы'

    def handle(self, *args, **options):
        # ─── Ensure workout types exist ──
        WORKOUT_TYPES_DATA = [
            ('Групповая тренировка', 'other', 'Общая групповая тренировка'),
            ('Персональная тренировка', 'other', 'Индивидуальная тренировка'),
            ('Йога', 'calm', 'Классическая йога'),
            ('Stretch Basic', 'calm', 'Базовый стретчинг'),
            ('Deep Stretch', 'calm', 'Глубокий стретчинг'),
            ('Pilates Basic', 'calm', 'Базовый пилатес'),
            ('Pilates Advanced', 'calm', 'Продвинутый пилатес'),
            ('Pilates', 'calm', 'Пилатес'),
            ('Zumba', 'dance', 'Танцевальный фитнес'),
            ('Dance Mix', 'dance', 'Микс танцевальных стилей'),
            ('Functional Training', 'strength', 'Функциональная тренировка'),
            ('Step Aerobics', 'cardio', 'Степ-аэробика'),
            ('Body Sculpt', 'strength', 'Коррекция фигуры'),
            ('HIIT', 'cardio', 'Интервальная тренировка'),
            ('Boxing', 'strength', 'Бокс'),
            ('Kickboxing', 'strength', 'Кикбоксинг'),
            ('Stretching', 'calm', 'Растяжка'),
            ('TRX', 'strength', 'Петли TRX'),
            ('Aerial Yoga', 'calm', 'Йога в гамаках'),
            ('Meditation', 'calm', 'Медитация'),
            ('Dance', 'dance', 'Современные танцы'),
            ('Cardio', 'cardio', 'Кардио'),
            ('Strength', 'strength', 'Силовая'),
            ('Flexibility', 'calm', 'Гибкость'),
        ]
        self.stdout.write('Обеспечиваю наличие типов тренировок...')
        wt_map = {}
        for name, cat, desc in WORKOUT_TYPES_DATA:
            wt, _ = WorkoutType.objects.get_or_create(
                name=name, defaults={'category': cat, 'description': desc}
            )
            if wt.category != cat:
                wt.category = cat
                wt.description = desc
                wt.save()
            wt_map[name] = wt
        self.stdout.write(self.style.SUCCESS(f'  {WorkoutType.objects.count()} типов готово'))

        # ─── Manager reference ──
        manager = User.objects.filter(is_superuser=True).first()
        if not manager:
            manager = UserProfile.objects.filter(role='manager').select_related('user').first()
            manager = manager.user if manager else None

        # ─── Trainers data ──
        TRAINERS = [
            {
                'username': 'arina.fedotova',
                'password': 'ArinaTrainer2025!',
                'first_name': 'Арина',
                'last_name': 'Федотова',
                'patronymic': 'Денисовна',
                'phone': '+7 (925) 456-78-90',
                'email': 'arina.fedotova@fitclub.ru',
                'bio': (
                    'Сертифицированный инструктор по йоге и стретчингу с 5-летним стажем. '
                    'Прошла обучение в Индии по направлению Hatha Yoga. '
                    'Специализируется на восстановительных практиках, йога-терапии и медитации. '
                    'Ведёт групповые и индивидуальные занятия.'
                ),
                'workouts': ['Йога', 'Aerial Yoga', 'Meditation', 'Stretching', 'Flexibility'],
                'max_hours': 40,
                'min_hours': 15,
                'hourly_rate': '450.00',
                'substitute_priority': 30,
                'preferred_shifts': 'Утро (08:00–12:00), День (12:00–16:00)',
                'unavailable_days': 'Среда',
            },
            {
                'username': 'evgeny.ryzhov',
                'password': 'EvgenyPower2025!',
                'first_name': 'Евгений',
                'last_name': 'Рыжов',
                'patronymic': 'Андреевич',
                'phone': '+7 (926) 789-01-23',
                'email': 'evgeny.ryzhov@fitclub.ru',
                'bio': (
                    'Мастер спорта по боксу, фитнес-тренер с 7-летним опытом. '
                    'Сертифицированный инструктор по HIIT, Functional Training и TRX. '
                    'Проводил мастер-классы по силовым тренировкам в Москве и Санкт-Петербурге. '
                    'Специализируется на функциональных и интервальных программах.'
                ),
                'workouts': ['Boxing', 'Kickboxing', 'HIIT', 'Strength', 'Functional Training', 'TRX'],
                'max_hours': 45,
                'min_hours': 15,
                'hourly_rate': '500.00',
                'substitute_priority': 25,
                'preferred_shifts': 'Вечер (16:00–22:00)',
                'unavailable_days': 'Понедельник',
            },
        ]

        NOW = timezone.now()
        all_slots = ['08:00-08:50', '09:00-09:50', '10:00-10:50',
                     '11:00-11:50', '12:00-12:50', '13:00-13:50',
                     '14:00-14:50', '15:00-15:50', '16:00-16:50',
                     '17:00-17:50', '18:00-18:50', '19:00-19:50',
                     '20:00-20:50', '21:00-21:50']
        sat_slots = all_slots[1:11]
        sun_slots = all_slots[2:8]

        def slots_for_date(d):
            wd = d.weekday()
            if wd == 6:
                return sun_slots
            if wd == 5:
                return sat_slots
            return all_slots

        def parse_ts(ts):
            parts = ts.split('-')
            return time.fromisoformat(parts[0]), time.fromisoformat(parts[1])

        def pick_workout(wts, ts):
            if not wts:
                return None
            hour = int(ts.split(':')[0])
            if 8 <= hour <= 11:
                calm = [w for w in wts if w.category == 'calm']
                if calm:
                    return random.choice(calm)
            elif hour >= 18:
                high = [w for w in wts if w.category in ('cardio', 'strength', 'dance')]
                if high:
                    return random.choice(high)
            return random.choice(wts)

        for tdata in TRAINERS:
            uname = tdata['username']

            # ── 1. Check if user already exists ──
            existing = User.objects.filter(username=uname).first()
            if existing:
                self.stdout.write(f'  Пользователь {uname} уже существует, пропускаю')
                continue

            # ── 2. Create User ──
            user = User.objects.create_user(
                username=uname,
                email=tdata['email'],
                first_name=tdata['first_name'],
                last_name=tdata['last_name'],
                password=tdata['password'],
            )
            user.is_active = True
            # Set date_joined to a month ago to simulate earlier registration
            user.date_joined = NOW - timedelta(days=35)
            user.save()

            self.stdout.write(f'  Создан пользователь: {tdata["first_name"]} {tdata["last_name"]} ({uname})')

            # ── 3. UserProfile ──
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = 'employee'
            profile.phone = tdata['phone']
            profile.patronymic = tdata['patronymic']
            # No invitation_timestamp → permanent password, no force change
            profile.invitation_timestamp = None
            profile.save()

            # ── 4. Employee ──
            emp, _ = Employee.objects.get_or_create(user_profile=profile)
            emp.is_substitute = True
            emp.substitute_priority = tdata['substitute_priority']
            emp.max_hours_per_week = tdata['max_hours']
            emp.min_hours_per_week = tdata['min_hours']
            emp.hourly_rate = tdata['hourly_rate']
            emp.qualifications = tdata['bio']
            emp.preferred_shifts = tdata['preferred_shifts']
            emp.unavailable_days = tdata['unavailable_days']
            emp.save()

            # Assign workout types
            wts_to_assign = [wt_map[n] for n in tdata['workouts'] if n in wt_map]
            emp.workout_types.set(wts_to_assign)
            self.stdout.write(f'    Назначено направлений: {len(wts_to_assign)}')

            # ── 5. Availability (past + future — 90 days total) ──
            self.stdout.write(f'    Создаю доступность...')
            av_count = 0
            start_av = date.today() - timedelta(days=30)
            for d_offset in range(90):  # 30 days past + 60 future
                d = start_av + timedelta(days=d_offset)
                # Skip the unavailable day each week (e.g. Wednesday for Arina)
            # We handle blocking per-day logic after
                day_name_ru = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'][d.weekday()]
                if day_name_ru == tdata['unavailable_days']:
                    continue
                for ts in slots_for_date(d):
                    st, et = parse_ts(ts)
                    _, created = Availability.objects.get_or_create(
                        employee=profile,
                        date=d,
                        start_time=st,
                        defaults={'end_time': et, 'is_available': True}
                    )
                    if created:
                        av_count += 1
            self.stdout.write(f'    Создано {av_count} записей доступности')

            # ── 6. Schedule history (past schedules with shifts) ──
            self.stdout.write(f'    Создаю историю смен...')
            shift_count = 0
            if manager:
                today = date.today()
                monday = today - timedelta(days=today.weekday())
                for week_offset in range(-4, 1):  # 4 past weeks + current
                    week_start = monday + timedelta(weeks=week_offset)
                    week_end = week_start + timedelta(days=6)
                    sched_name = f'Тренировки {week_start.strftime("%d.%m")}-{week_end.strftime("%d.%m")}'

                    sched, _ = Schedule.objects.get_or_create(
                        name=sched_name,
                        defaults={
                            'start_date': week_start,
                            'end_date': week_end,
                            'status': 'approved' if week_offset < 0 else 'pending',
                            'created_by': manager,
                        }
                    )

                    cur = week_start
                    used_week = ShiftAssignment.objects.filter(employee=profile, schedule__start_date=week_start).count()
                    while cur <= week_end:
                        day_name_ru = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'][cur.weekday()]
                        if day_name_ru == tdata['unavailable_days']:
                            cur += timedelta(days=1)
                            continue
                        daily_shifts = random.randint(1, min(4, len(slots_for_date(cur))))
                        existing_today = ShiftAssignment.objects.filter(employee=profile, date=cur).count()
                        slots_available = len(slots_for_date(cur)) - existing_today
                        if slots_available <= 0:
                            cur += timedelta(days=1)
                            continue
                        random_slots = random.sample(slots_for_date(cur), min(daily_shifts - existing_today, slots_available))
                        for ts in random_slots:
                            if used_week >= emp.max_hours_per_week:
                                break
                            st, et = parse_ts(ts)
                            wt = pick_workout(wts_to_assign, ts)
                            _, created = ShiftAssignment.objects.get_or_create(
                                schedule=sched,
                                employee=profile,
                                date=cur,
                                start_time=st,
                                defaults={
                                    'end_time': et,
                                    'workout_type': wt,
                                    'status': 'completed' if week_offset < -1 else ('confirmed' if week_offset < 0 else 'scheduled'),
                                    'actual_hours': 0.83 if week_offset < -1 else None,
                                }
                            )
                            if created:
                                shift_count += 1
                                used_week += 1
                        cur += timedelta(days=1)

                    # Create approval
                    if week_offset < 0 and not ScheduleApproval.objects.filter(schedule=sched, employee=profile).exists():
                        ScheduleApproval.objects.create(
                            schedule=sched,
                            employee=profile,
                            approved=True,
                            comment='Всё устраивает',
                            responded_at=NOW - timedelta(days=7),
                        )

                    # Create version snapshot if not exists
                    ver, ver_created = ScheduleVersion.objects.get_or_create(
                        schedule=sched,
                        version_number=1,
                        defaults={
                            'schedule_name': sched.name,
                            'created_by': manager,
                            'change_source': 'create',
                            'change_note': 'Первичное создание графика',
                        }
                    )
                    for sh in ShiftAssignment.objects.filter(schedule=sched, employee=profile):
                        ScheduleVersionAssignment.objects.get_or_create(
                            schedule_version=ver,
                            employee=sh.employee,
                            workout_type=sh.workout_type,
                            date=sh.date,
                            start_time=sh.start_time,
                            end_time=sh.end_time,
                        )

            self.stdout.write(f'    Создано {shift_count} смен в расписаниях')

            self.stdout.write(self.style.SUCCESS(f'  Тренер {tdata["first_name"]} {tdata["last_name"]} полностью создан'))

        # ─── Summary ──
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('ГОТОВО! Созданы 2 новых тренера.'))
        self.stdout.write('=' * 60)
        self.stdout.write('')
        self.stdout.write('ДАННЫЕ ДЛЯ ВХОДА:')
        self.stdout.write('-' * 40)
        for tdata in TRAINERS:
            self.stdout.write(f'  Логин:    {tdata["username"]}')
            self.stdout.write(f'  Пароль:   {tdata["password"]}')
            self.stdout.write(f'  Имя:      {tdata["first_name"]} {tdata["last_name"]}')
            self.stdout.write(f'  Телефон:  {tdata["phone"]}')
            self.stdout.write(f'  Направления: {", ".join(tdata["workouts"])}')
            self.stdout.write('')
        self.stdout.write('Вход: http://127.0.0.1:8000/login/')
