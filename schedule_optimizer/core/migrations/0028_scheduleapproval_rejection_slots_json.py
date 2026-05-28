from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_shiftswaprequest_to_employee_nullable'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheduleapproval',
            name='rejection_slots_json',
            field=models.JSONField(blank=True, default=list),
        ),
    ]

