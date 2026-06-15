import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE','schedule_optimizer.settings')
sys.path.insert(0, r'C:\Users\miles\Desktop\учеба\4 rehc\курсач\программа\cursach_flexible_schedule\schedule_optimizer')
django.setup()
from django.db import connection
from core.models import *

# Check raw table counts
with connection.cursor() as cursor:
    cursor.execute("SELECT count(*) FROM core_shiftswaprequest")
    print(f'Raw core_shiftswaprequest count: {cursor.fetchone()[0]}')
    cursor.execute("SELECT count(*) FROM core_swapshift")
    print(f'Raw core_swapshift count: {cursor.fetchone()[0]}')
    cursor.execute("SELECT * FROM core_swapshift")
    rows = cursor.fetchall()
    print(f'SwapShift rows: {rows}')

print()
# Show all users with readable names
print('=== USERS WITH NAMES ===')
for u in User.objects.all().order_by('id'):
    print(f'ID:{u.id} | {u.username} | email:{u.email} | first:{u.first_name!r} | last:{u.last_name!r} | is_staff:{u.is_staff} | is_superuser:{u.is_superuser}')

print()
# Show swap requests without shifts
for req in ShiftSwapRequest.objects.all():
    print(f'Req {req.id}: shifts count = {req.shifts.count()}')
