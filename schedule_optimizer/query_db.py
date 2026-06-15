import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE','schedule_optimizer.settings')
sys.path.insert(0, r'C:\Users\miles\Desktop\учеба\4 rehc\курсач\программа\cursach_flexible_schedule\schedule_optimizer')
django.setup()
from django.contrib.auth.models import User
from core.models import *

print('=== USERS ===')
for u in User.objects.all().order_by('id'):
    role = u.profile.role if hasattr(u, 'profile') else 'NOPROFILE'
    emp_id = u.profile.employee_profile.id if hasattr(u, 'profile') and hasattr(u.profile, 'employee_profile') else None
    print(f'ID:{u.id} | {u.username} | {u.first_name} {u.last_name} | is_active:{u.is_active} | role:{role} | employee_id:{emp_id}')

print()
print('=== WORKOUT TYPES ===')
for wt in WorkoutType.objects.all():
    print(f'ID:{wt.id} | {wt.name} | cat:{wt.category}')

print()
print('=== SCHEDULES ===')
for s in Schedule.objects.all().order_by('-created_at'):
    print(f'ID:{s.id} | "{s.name}" | {s.start_date} -> {s.end_date} | status:{s.status} | created_by:{s.created_by}')

print()
print('=== SHIFT SWAP REQUESTS ===')
for req in ShiftSwapRequest.objects.all():
    print(f'ID:{req.id} | from_emp:{req.from_employee} | to_emp:{req.to_employee} | status:{req.status} | reason:"{str(req.reason)[:60]}" | created:{req.created_at}')
    for sw in req.shifts.all():
        print(f'   SwapShift ID:{sw.id} -> ShiftAssignment ID:{sw.shift_assignment_id}')

print()
print('=== SHIFT ASSIGNMENTS (first 30) ===')
for a in ShiftAssignment.objects.all().select_related('employee__user', 'workout_type', 'schedule')[:30]:
    print(f'ID:{a.id} | schedule:{a.schedule_id} | emp:{a.employee} | wt:{a.workout_type} | date:{a.date} | {a.start_time}-{a.end_time} | status:{a.status}')

print()
print('=== AVAILABILITY (first 30) ===')
for a in Availability.objects.all()[:30]:
    print(f'ID:{a.id} | emp:{a.employee} | date:{a.date} | {a.start_time}-{a.end_time} | avail:{a.is_available}')

print()
print('=== TOTALS ===')
print(f'Users:{User.objects.count()} UserProfiles:{UserProfile.objects.count()} Employees:{Employee.objects.count()} WorkoutTypes:{WorkoutType.objects.count()} Schedules:{Schedule.objects.count()} ShiftAssignments:{ShiftAssignment.objects.count()} ShiftSwapRequests:{ShiftSwapRequest.objects.count()} SwapShifts:{SwapShift.objects.count()} Availabilities:{Availability.objects.count()}')
