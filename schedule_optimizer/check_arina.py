import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schedule_optimizer.settings')
import django
django.setup()
from core.models import UserProfile, ShiftAssignment

a = UserProfile.objects.filter(user__username__icontains='arina').first()
print('Arina profile:', a.id if a else 'NOT FOUND')
if a:
    shifts = ShiftAssignment.objects.filter(employee=a).select_related('workout_type','schedule').order_by('-date')[:10]
    for x in shifts:
        wt = x.workout_type.name if x.workout_type else 'NULL'
        print(f'ID={x.id} date={x.date} time={x.start_time} wt={wt} sched={x.schedule.name}')
