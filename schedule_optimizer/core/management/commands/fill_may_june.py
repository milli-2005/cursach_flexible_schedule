"""Fill May-June schedules with all employees and create 10 swap records."""
import random
from datetime import date, time, datetime, timedelta
from datetime import timezone as dt_timezone

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    UserProfile, Employee, WorkoutType, Schedule, ShiftAssignment,
    ScheduleApproval, ScheduleVersion, ScheduleVersionAssignment,
    ShiftSwapRequest, SwapShift, Availability,
)


class Command(BaseCommand):
    help = 'Fill May-June schedules + 10 swap requests'

    def handle(self, *args, **options):
        NOW = timezone.now()

        ALL_SLOTS = ['08:00-08:50', '09:00-09:50', '10:00-10:50',
                     '11:00-11:50', '12:00-12:50', '13:00-13:50',
                     '14:00-14:50', '15:00-15:50', '16:00-16:50',
                     '17:00-17:50', '18:00-18:50', '19:00-19:50',
                     '20:00-20:50', '21:00-21:50']
        SAT_SLOTS = ALL_SLOTS[1:11]
        SUN_SLOTS = ALL_SLOTS[2:8]

        def slots_for_date(d):
            wd = d.weekday()
            if wd == 6: return SUN_SLOTS
            if wd == 5: return SAT_SLOTS
            return ALL_SLOTS

        def parse_ts(ts):
            parts = ts.split('-')
            return time.fromisoformat(parts[0]), time.fromisoformat(parts[1])

        employees = Employee.objects.filter(
            user_profile__role='employee'
        ).select_related('user_profile__user').prefetch_related('workout_types')

        emp_list = []
        for emp in employees:
            wts = list(emp.workout_types.all())
            if wts:
                emp_list.append({
                    'emp': emp,
                    'profile': emp.user_profile,
                    'user': emp.user_profile.user,
                    'wts': wts,
                })

        managers = User.objects.filter(
            profile__role='manager', is_active=True
        )
        manager_user = managers.first()
        if not manager_user:
            manager_user = User.objects.filter(is_superuser=True).first()

        self.stdout.write(f'Сотрудников: {len(emp_list)}, менеджеров: {managers.count()}')

        WEEK_DEFS = []
        start = date(2026, 5, 4)
        for i in range(7):
            ws = start + timedelta(weeks=i)
            we = ws + timedelta(days=6)
            WEEK_DEFS.append({
                'start': ws, 'end': we,
                'name': f'Расписание {ws.strftime("%d.%m")}-{we.strftime("%d.%m")}',
                'status': 'approved' if we < date.today() else 'pending',
            })

        sched_names = [w['name'] for w in WEEK_DEFS]

        # Clean up old data for these weeks
        self.stdout.write('Очищаю старые данные...')
        for s in Schedule.objects.filter(name__in=sched_names):
            self.stdout.write(f'  {s.name}')
            s.delete()
        self.stdout.write(self.style.SUCCESS('  Очищено'))

        # Create schedules
        total_shifts = 0
        for wdef in WEEK_DEFS:
            sched = Schedule.objects.create(
                name=wdef['name'],
                start_date=wdef['start'],
                end_date=wdef['end'],
                status=wdef['status'],
                created_by=manager_user,
            )

            cur = wdef['start']
            while cur <= wdef['end']:
                day_slots = slots_for_date(cur)
                n = len(day_slots)

                def find_block(segments, min_len=2, max_len=4):
                    """Pick a random consecutive block from available segments."""
                    candidates = []
                    for seg_start, seg_end in segments:
                        seg_size = seg_end - seg_start
                        if seg_size < min_len:
                            continue
                        for bsize in range(min_len, min(max_len, seg_size) + 1):
                            max_start = seg_end - bsize
                            for s in range(seg_start, max_start + 1):
                                candidates.append((s, bsize))
                    if not candidates:
                        return None
                    return random.choice(candidates)

                segments = [(0, n)]
                random.shuffle(emp_list)
                for emp_data in emp_list:
                    if len(segments) == 0:
                        break
                    if random.random() < 0.25:
                        continue
                    block = find_block(segments, min_len=2, max_len=4)
                    if not block:
                        continue
                    start_idx, block_len = block

                    new_segments = []
                    for seg_start, seg_end in segments:
                        if seg_end <= start_idx or seg_start >= start_idx + block_len:
                            new_segments.append((seg_start, seg_end))
                        else:
                            if seg_start < start_idx:
                                new_segments.append((seg_start, start_idx))
                            if seg_end > start_idx + block_len:
                                new_segments.append((start_idx + block_len, seg_end))
                    segments = new_segments

                    for idx in range(start_idx, start_idx + block_len):
                        ts = day_slots[idx]
                        st, et = parse_ts(ts)
                        is_past = cur < date.today()
                        wt = random.choice(emp_data['wts'])
                        ShiftAssignment.objects.create(
                            schedule=sched,
                            employee=emp_data['profile'],
                            date=cur, start_time=st, end_time=et,
                            workout_type=wt,
                            status='completed' if is_past else 'scheduled',
                            actual_hours=0.83 if is_past else None,
                        )
                        total_shifts += 1
                cur += timedelta(days=1)

            sc = ShiftAssignment.objects.filter(schedule=sched).count()
            ec = ShiftAssignment.objects.filter(schedule=sched).values('employee').distinct().count()
            self.stdout.write(f'  id={sched.id} shifts={sc} employees={ec}')

            # Generate varied approval data based on week
            week_index = WEEK_DEFS.index(wdef)
            if week_index == 0:      # May 4  - 90% respond
                respond_pct = 0.9
            elif week_index == 1:    # May 11 - 80%
                respond_pct = 0.8
            elif week_index == 2:    # May 18 - 100%
                respond_pct = 1.0
            elif week_index == 3:    # May 25 - 100%
                respond_pct = 1.0
            elif week_index == 4:    # Jun 1  - 70%
                respond_pct = 0.7
            elif week_index == 5:    # Jun 8  - 90%
                respond_pct = 0.9
            else:                    # Jun 15 - 80% (current)
                respond_pct = 0.8

            emp_ids = list(ShiftAssignment.objects.filter(
                schedule=sched
            ).values_list('employee_id', flat=True).distinct())
            random.shuffle(emp_ids)
            respond_count = max(1, int(len(emp_ids) * respond_pct))
            for i, eid in enumerate(emp_ids):
                eprof = UserProfile.objects.get(id=eid)
                has_responded = i < respond_count
                if has_responded:
                    # Approved schedules cannot have rejections; only pending can
                    can_reject = sched.status == 'pending'
                    approve = False if (can_reject and random.random() < 0.15) else True
                    ScheduleApproval.objects.get_or_create(
                        schedule=sched, employee=eprof,
                        defaults={
                            'approved': approve,
                            'comment': 'Всё устраивает' if approve else 'Нужна замена на этот день',
                            'responded_at': datetime.combine(
                                sched.start_date + timedelta(days=random.randint(1, 3)),
                                time(random.randint(8, 18), 0), tzinfo=dt_timezone.utc
                            ),
                        }
                    )
                else:
                    ScheduleApproval.objects.get_or_create(
                        schedule=sched, employee=eprof,
                        defaults={'approved': None, 'comment': '', 'responded_at': None},
                    )

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

        self.stdout.write(self.style.SUCCESS(f'\nВсего смен: {total_shifts}'))

        # Create 10 swap requests with real past dates across May-June
        self.stdout.write('\nСоздаю заявки на обмен (прошедшие, май-июнь)...')
        SwapShift.objects.all().delete()
        ShiftSwapRequest.objects.all().delete()

        today = date.today()
        may_june_scheds = Schedule.objects.filter(name__in=sched_names)
        may_june_shifts = ShiftAssignment.objects.filter(
            schedule__in=may_june_scheds,
            date__lt=today,  # only past shifts
        )

        swap_scenarios = [
            {'reason': 'Срочное дело, нужно заменить утреннюю смену', 'status': 'completed',
             'fi': 0, 'ti': 1, 'created': date(2026, 5, 7)},
            {'reason': 'Заболела, нужна замена на среду', 'status': 'completed',
             'fi': 2, 'ti': 3, 'created': date(2026, 5, 13)},
            {'reason': 'Семейные обстоятельства, поменяйтесь со мной', 'status': 'completed',
             'fi': 4, 'ti': 5, 'created': date(2026, 5, 19)},
            {'reason': 'Не успеваю на вечернюю тренировку', 'status': 'approved_by_manager',
             'fi': 6, 'ti': 7, 'created': date(2026, 5, 25)},
            {'reason': 'Нужно отлучиться днём, помогите', 'status': 'approved_by_employee',
             'fi': 8, 'ti': 0, 'created': date(2026, 6, 2)},
            {'reason': 'Перепутал даты, нужна замена', 'status': 'pending',
             'fi': 1, 'ti': 2, 'created': date(2026, 6, 9)},
            {'reason': 'Плохо себя чувствую, замените пожалуйста', 'status': 'pending',
             'fi': 3, 'ti': None, 'created': date(2026, 6, 14)},
            {'reason': 'Важная встреча, не могу выйти', 'status': 'rejected',
             'fi': 5, 'ti': 6, 'created': date(2026, 5, 10)},
            {'reason': 'Хочу поменяться чтобы взять дополнительные часы', 'status': 'rejected',
             'fi': 7, 'ti': 4, 'created': date(2026, 5, 22)},
            {'reason': 'Двойная запись в графике, исправьте', 'status': 'completed',
             'fi': 8, 'ti': 0, 'created': date(2026, 6, 5)},
        ]

        created = 0
        for sc in swap_scenarios:
            if created >= 10:
                break
            from_emp = employees[sc['fi'] % len(employees)]
            to_emp = employees[sc['ti'] % len(employees)] if sc['ti'] is not None else None
            # Pick shifts that are on or before the creation date
            shifts = may_june_shifts.filter(
                employee=from_emp.user_profile,
                date__lte=sc['created'],
            ).order_by('?')[:2]
            if shifts.count() < 2:
                # Fallback: any past shift for this employee
                shifts = may_june_shifts.filter(
                    employee=from_emp.user_profile,
                ).order_by('?')[:2]
            if shifts.count() == 0:
                continue
            # Create and then override created_at (bypass auto_now_add)
            req = ShiftSwapRequest.objects.create(
                from_employee=from_emp, to_employee=to_emp,
                reason=sc['reason'], status=sc['status'],
            )
            ShiftSwapRequest.objects.filter(pk=req.pk).update(
                created_at=datetime.combine(sc['created'], time(10, 0), tzinfo=dt_timezone.utc)
            )
            for sh in shifts:
                SwapShift.objects.create(swap_request=req, shift_assignment=sh)
            created += 1
            fn = from_emp.user_profile.user.first_name
            tn = to_emp.user_profile.user.first_name if to_emp else '-'
            self.stdout.write(f'  [{created}] {sc["created"]} {fn} -> {tn}: {sc["status"]}')

        self.stdout.write(self.style.SUCCESS(f'\nЗаявок: {created}'))

        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('ГОТОВО!'))
        self.stdout.write('=' * 60)
        total = ShiftAssignment.objects.filter(schedule__in=Schedule.objects.filter(name__in=sched_names)).count()
        self.stdout.write(f'Графиков: {len(WEEK_DEFS)}, смен: {total}')
        self.stdout.write(f'Заявок на обмен: {ShiftSwapRequest.objects.count()}, привязок: {SwapShift.objects.count()}')
