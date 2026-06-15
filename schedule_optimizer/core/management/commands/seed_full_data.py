"""Seed full test data: 12 users, workout types, schedules Apr-June 2026."""
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
    help = 'Создаёт полные тестовые данные: пользователи, графики, согласования'

    def handle(self, *args, **options):
        self.PASSWORD = 'test12345'

        # ─── 0. CLEANUP ──
        self.stdout.write('Очищаю старые данные...')
        ScheduleVersionAssignment.objects.all().delete()
        ScheduleVersion.objects.all().delete()
        ScheduleApproval.objects.all().delete()
        ShiftAssignment.objects.all().delete()
        Availability.objects.all().delete()
        Schedule.objects.all().delete()
        Employee.objects.all().delete()
        UserProfile.objects.all().delete()
        User.objects.exclude(is_superuser=True).delete()
        WorkoutType.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('  Все старые данные удалены (кроме superuser)'))

        # ─── 1. WORKOUT TYPES ──
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
        self.stdout.write('Создаю типы тренировок...')
        wt_map = {}
        for name, cat, desc in WORKOUT_TYPES_DATA:
            wt, _ = WorkoutType.objects.get_or_create(
                name=name, defaults={'category': cat, 'description': desc}
            )
            if wt.category != cat:
                wt.category = cat; wt.description = desc; wt.save()
            wt_map[name] = wt
        self.stdout.write(self.style.SUCCESS(f'  {WorkoutType.objects.count()} типов готово'))

        # ─── 2. USERS ──
        USERS_DATA = [
            ('anna.sokolova', 'Анна', 'Соколова', 'Алексеевна', '+7 (916) 123-45-01', 'employee',
             ['Йога', 'Aerial Yoga', 'Meditation', 'Stretching']),
            ('elena.morozova', 'Елена', 'Морозова', 'Игоревна', '+7 (916) 123-45-02', 'employee',
             ['Zumba', 'Dance Mix', 'Dance', 'Step Aerobics']),
            ('dmitry.volkov', 'Дмитрий', 'Волков', 'Сергеевич', '+7 (916) 123-45-03', 'employee',
             ['Boxing', 'Kickboxing', 'HIIT', 'Strength']),
            ('olga.belova', 'Ольга', 'Белова', 'Николаевна', '+7 (916) 123-45-04', 'employee',
             ['Pilates Basic', 'Pilates Advanced', 'Pilates', 'Deep Stretch']),
            ('sergey.kuznetsov', 'Сергей', 'Кузнецов', 'Петрович', '+7 (916) 123-45-05', 'employee',
             ['Functional Training', 'TRX', 'Body Sculpt']),
            ('maria.lebedeva', 'Мария', 'Лебедева', 'Дмитриевна', '+7 (916) 123-45-06', 'employee',
             ['Stretch Basic', 'Deep Stretch', 'Flexibility', 'Pilates']),
            ('alexey.popov', 'Алексей', 'Попов', 'Владимирович', '+7 (916) 123-45-07', 'employee',
             ['Step Aerobics', 'Cardio', 'HIIT', 'Functional Training']),
            ('natalia.krylova', 'Наталья', 'Крылова', 'Сергеевна', '+7 (916) 123-45-08', 'employee',
             ['Групповая тренировка', 'Персональная тренировка']),
            ('ivan.titov', 'Иван', 'Титов', 'Олегович', '+7 (916) 123-45-09', 'employee',
             ['Strength', 'Body Sculpt', 'Functional Training']),
            ('kristina.orlova', 'Кристина', 'Орлова', 'Андреевна', '+7 (916) 123-45-10', 'employee',
             ['Dance Mix', 'Zumba', 'Dance', 'Cardio']),
            ('victoria.pavlova', 'Виктория', 'Павлова', 'Михайловна', '+7 (916) 123-45-11', 'manager', []),
            ('mikhail.sokolov', 'Михаил', 'Соколов', 'Антонович', '+7 (916) 123-45-12', 'manager', []),
        ]

        self.stdout.write('Создаю пользователей...')
        created = {}
        for username, fn, ln, patr, phone, role, wt_names in USERS_DATA:
            user, _ = User.objects.get_or_create(username=username)
            user.set_password(self.PASSWORD)
            user.first_name = fn
            user.last_name = ln
            user.email = f'{username}@fitclub.ru'
            user.is_active = True
            user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.phone = phone
            profile.patronymic = patr
            profile.save()

            emp, _ = Employee.objects.get_or_create(user_profile=profile)
            emp.is_substitute = True
            emp.substitute_priority = random.randint(10, 60)
            emp.max_hours_per_week = 40
            emp.min_hours_per_week = 12
            emp.save()

            if role == 'employee':
                emp.workout_types.set([wt_map[n] for n in wt_names])

            created[username] = (user, profile)
            self.stdout.write(f'  {fn} {ln} ({role}) — логин: {username}, пароль: {self.PASSWORD}')

        # ─── 3. TIME SLOTS ──
        ALL_SLOTS = ['08:00-08:50', '09:00-09:50', '10:00-10:50',
                     '11:00-11:50', '12:00-12:50', '13:00-13:50',
                     '14:00-14:50', '15:00-15:50', '16:00-16:50',
                     '17:00-17:50', '18:00-18:50', '19:00-19:50',
                     '20:00-20:50', '21:00-21:50']
        SAT_SLOTS = ALL_SLOTS[1:11]  # 09:00-19:00
        SUN_SLOTS = ALL_SLOTS[2:8]   # 10:00-16:00

        def slots_for_date(d):
            wd = d.weekday()
            if wd == 6: return SUN_SLOTS
            if wd == 5: return SAT_SLOTS
            return ALL_SLOTS

        def parse_ts(ts):
            parts = ts.split('-')
            return time.fromisoformat(parts[0]), time.fromisoformat(parts[1])

        # ─── 4. AVAILABILITY ──
        self.stdout.write('Создаю доступность сотрудников...')
        av_count = 0
        for username, fn, ln, patr, phone, role, _ in USERS_DATA:
            if role == 'manager': continue
            _, profile = created[username]
            for d_offset in range(60):
                d = date(2026, 4, 6) + timedelta(days=d_offset)
                for ts in slots_for_date(d):
                    st, et = parse_ts(ts)
                    _, ok = Availability.objects.get_or_create(
                        employee=profile, date=d, start_time=st,
                        defaults={'end_time': et, 'is_available': True}
                    )
                    if ok: av_count += 1
        self.stdout.write(self.style.SUCCESS(f'  {av_count} записей доступности'))

        # ─── 5. SCHEDULES ──
        manager_user, _ = created['victoria.pavlova']

        trainer_wt_map = {}
        for username, fn, ln, patr, phone, role, wt_names in USERS_DATA:
            if role == 'employee':
                trainer_wt_map[username] = wt_names

        SCHEDULE_DEFS = [
            {'name': 'Апрель — неделя 1 (6–12 апреля)',
             'start': date(2026, 4, 6), 'end': date(2026, 4, 12), 'status': 'approved',
             'rejections': {}},
            {'name': 'Апрель — неделя 2 (13–19 апреля)',
             'start': date(2026, 4, 13), 'end': date(2026, 4, 19), 'status': 'approved',
             'rejections': {'olga.belova': [('2026-04-15', '18:00-18:50')]}},
            {'name': 'Апрель — неделя 3 (20–26 апреля)',
             'start': date(2026, 4, 20), 'end': date(2026, 4, 26), 'status': 'approved',
             'rejections': {'elena.morozova': [('2026-04-22', '10:00-10:50')],
                            'dmitry.volkov': [('2026-04-23', '14:00-14:50'), ('2026-04-25', '11:00-11:50')]}},
            {'name': 'Апрель — неделя 4 (27 апр – 3 мая)',
             'start': date(2026, 4, 27), 'end': date(2026, 5, 3), 'status': 'pending',
             'rejections': {'natalia.krylova': [('2026-04-29', '09:00-09:50')]}},
            {'name': 'Май — неделя 1 (4–10 мая)',
             'start': date(2026, 5, 4), 'end': date(2026, 5, 10), 'status': 'pending',
             'rejections': {}},
            {'name': 'Май — неделя 2 (11–17 мая)',
             'start': date(2026, 5, 11), 'end': date(2026, 5, 17), 'status': 'draft',
             'rejections': {}},
            {'name': 'Май — неделя 3 (18–24 мая)',
             'start': date(2026, 5, 18), 'end': date(2026, 5, 24), 'status': 'draft',
             'rejections': {}},
            {'name': 'Май — неделя 4 (25–31 мая)',
             'start': date(2026, 5, 25), 'end': date(2026, 5, 31), 'status': 'draft',
             'rejections': {}},
            {'name': 'Июнь — неделя (22–28 июня)',
             'start': date(2026, 6, 22), 'end': date(2026, 6, 28), 'status': 'pending',
             'rejections': {}},
        ]

        def pick_trainer(d, ts, used_today, used_week, exclude=set()):
            hour = int(ts.split(':')[0])
            if 8 <= hour <= 11:
                pool = ['anna.sokolova', 'olga.belova', 'maria.lebedeva']
            elif 11 < hour <= 14:
                pool = ['dmitry.volkov', 'sergey.kuznetsov', 'alexey.popov', 'ivan.titov']
            elif 14 < hour <= 16:
                pool = ['natalia.krylova', 'kristina.orlova', 'elena.morozova']
            else:
                pool = [u for u, *_2 in USERS_DATA
                        if u not in exclude and u not in ('victoria.pavlova', 'mikhail.sokolov')]
            pool = [u for u in pool if u not in exclude]
            if not pool:
                pool = [u for u, *_2 in USERS_DATA
                        if u not in exclude and u not in ('victoria.pavlova', 'mikhail.sokolov')]
            pool.sort(key=lambda u: (used_week.get(u, 0), used_today.get(u, 0)))
            return pool[0]

        def pick_workout(tname, ts):
            wts = [wt_map[n] for n in trainer_wt_map.get(tname, [])]
            if not wts: return None
            hour = int(ts.split(':')[0])
            if 8 <= hour <= 11:
                calm = [w for w in wts if w.category == 'calm']
                if calm: return calm[0]
            elif hour >= 18:
                high = [w for w in wts if w.category in ('cardio', 'strength', 'dance')]
                if high: return high[0]
            return wts[0]

        for sdef in SCHEDULE_DEFS:
            name = sdef['name']
            if Schedule.objects.filter(name=name).exists():
                self.stdout.write(f'График "{name}" уже существует, пропускаю')
                continue

            self.stdout.write(f'Создаю график: {name}...')
            sched = Schedule.objects.create(
                name=name, start_date=sdef['start'], end_date=sdef['end'],
                status=sdef['status'], created_by=manager_user,
            )

            used_week = {}
            cur = sdef['start']
            while cur <= sdef['end']:
                used_today = {}
                for ts in slots_for_date(cur):
                    tname = pick_trainer(cur, ts, used_today, used_week)
                    used_today[tname] = used_today.get(tname, 0) + 1
                    used_week[tname] = used_week.get(tname, 0) + 1
                    wt = pick_workout(tname, ts)
                    st, et = parse_ts(ts)
                    _, tprof = created[tname]
                    ShiftAssignment.objects.create(
                        schedule=sched, employee=tprof, workout_type=wt,
                        date=cur, start_time=st, end_time=et, status='scheduled',
                    )
                cur += timedelta(days=1)

            # Version v1
            ver = ScheduleVersion.objects.create(
                schedule=sched, version_number=1,
                schedule_name=sched.name, created_by=manager_user,
                change_source='create', change_note='Первичное создание графика',
            )
            for sh in ShiftAssignment.objects.filter(schedule=sched):
                ScheduleVersionAssignment.objects.create(
                    schedule_version=ver, employee=sh.employee,
                    workout_type=sh.workout_type, date=sh.date,
                    start_time=sh.start_time, end_time=sh.end_time,
                )

            # Approvals
            emp_ids = ShiftAssignment.objects.filter(schedule=sched).values_list('employee_id', flat=True).distinct()
            for eid in emp_ids:
                eprof = UserProfile.objects.get(id=eid)
                sa, _ = ScheduleApproval.objects.get_or_create(schedule=sched, employee=eprof)
                rejs = sdef['rejections'].get(eprof.user.username, [])
                if rejs:
                    sa.approved = False
                    sa.comment = 'Нужна замена на некоторые слоты'
                    sa.rejection_slots_json = [{'date': r[0], 'start_time': r[1]} for r in rejs]
                    sa.responded_at = timezone.now()
                elif sdef['status'] == 'approved':
                    sa.approved = True
                    sa.comment = 'Всё устраивает'
                    sa.responded_at = timezone.now()
                sa.save()

            sh_count = ShiftAssignment.objects.filter(schedule=sched).count()
            ap_count = ScheduleApproval.objects.filter(schedule=sched).count()
            self.stdout.write(self.style.SUCCESS(f'  id={sched.id} shifts={sh_count} approvals={ap_count}'))

        # ─── SUMMARY ──
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('ГОТОВО! Все данные созданы.'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'Типов тренировок: {WorkoutType.objects.count()}')
        self.stdout.write(f'Пользователей: {User.objects.count()}')
        self.stdout.write(f'Сотрудников: {Employee.objects.count()}')
        self.stdout.write(f'Графиков: {Schedule.objects.count()}')
        self.stdout.write(f'Смен: {ShiftAssignment.objects.count()}')
        self.stdout.write(f'Согласований: {ScheduleApproval.objects.count()}')
        self.stdout.write(f'Версий: {ScheduleVersion.objects.count()}')
        self.stdout.write('')
        self.stdout.write('ЛОГИНЫ И ПАРОЛИ (пароль для всех: test12345)')
        self.stdout.write('-' * 60)
        self.stdout.write(f'{"Логин":25s} {"Имя":20s} {"Роль":12s}')
        self.stdout.write('-' * 60)
        for username, fn, ln, patr, phone, role, _ in USERS_DATA:
            rd = 'Руководитель' if role == 'manager' else 'Тренер'
            self.stdout.write(f'{username:25s} {fn + " " + ln:20s} {rd:12s}')
        self.stdout.write('')
        self.stdout.write('Вход: http://127.0.0.1:8000/login/')
