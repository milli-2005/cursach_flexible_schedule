import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE','schedule_optimizer.settings')
sys.path.insert(0, r'C:\Users\miles\Desktop\учеба\4 rehc\курсач\программа\cursach_flexible_schedule\schedule_optimizer')
django.setup()
from core.models import *

# Show swap requests with shift details
print('=== ALL SWAP REQUESTS WITH SHIFT DETAILS ===')
for req in ShiftSwapRequest.objects.all():
    print(f'Request ID:{req.id} status:{req.status}')
    print(f'  From: {req.from_employee} (ID:{req.from_employee_id})')
    print(f'  To: {req.to_employee} (ID:{req.to_employee_id})')
    print(f'  Reason: {req.reason}')
    for sw in req.shifts.all():
        sa = sw.shift_assignment
        print(f'  SWAPSHIFT ID:{sw.id} -> ShiftAssignment ID:{sa.id} date:{sa.date} {sa.start_time} emp:{sa.employee} wt:{sa.workout_type} schedule:{sa.schedule_id}')

# Show all employee names properly
print()
print('=== ALL EMPLOYEES ===')
for e in Employee.objects.all().select_related('user_profile__user'):
    u = e.user_profile.user
    print(f'ID:{e.id} profile_id:{e.user_profile_id} username:{u.username} name:{u.last_name} {u.first_name} role:{e.user_profile.role} is_substitute:{e.is_substitute}')

print()
print('=== SwapShift count check ===')
print(f'SwapShift.objects.count() = {SwapShift.objects.count()}')
# Check if prefetch is working
for req in ShiftSwapRequest.objects.all()[:1]:
    print(f'Request {req.id} has shifts: {list(req.shifts.all())}')

