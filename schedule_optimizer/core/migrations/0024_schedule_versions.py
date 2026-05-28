from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_distributionrule'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ScheduleVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version_number', models.PositiveIntegerField(verbose_name='Номер версии')),
                ('schedule_name', models.CharField(max_length=200, verbose_name='Название графика в версии')),
                ('change_source', models.CharField(blank=True, help_text='create, update, restore', max_length=30, verbose_name='Источник изменения')),
                ('change_note', models.CharField(blank=True, max_length=255, verbose_name='Комментарий к версии')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания версии')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_schedule_versions', to=settings.AUTH_USER_MODEL, verbose_name='Кто создал версию')),
                ('schedule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='core.schedule', verbose_name='График')),
            ],
            options={
                'verbose_name': 'Версия графика',
                'verbose_name_plural': 'Версии графиков',
                'ordering': ['-version_number', '-id'],
            },
        ),
        migrations.CreateModel(
            name='ScheduleVersionAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Дата')),
                ('start_time', models.TimeField(verbose_name='Время начала')),
                ('end_time', models.TimeField(verbose_name='Время окончания')),
                ('employee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.userprofile', verbose_name='Сотрудник')),
                ('schedule_version', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='core.scheduleversion', verbose_name='Версия графика')),
                ('workout_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.workouttype', verbose_name='Тип занятия')),
            ],
            options={
                'verbose_name': 'Снимок смены версии',
                'verbose_name_plural': 'Снимки смен версий',
                'ordering': ['date', 'start_time', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='scheduleversion',
            constraint=models.UniqueConstraint(fields=('schedule', 'version_number'), name='unique_schedule_version_number'),
        ),
    ]

