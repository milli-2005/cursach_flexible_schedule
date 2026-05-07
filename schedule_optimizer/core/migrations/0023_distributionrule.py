from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_seed_hourratechange'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DistributionRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Название правила')),
                ('source_text', models.TextField(verbose_name='Текст правила')),
                ('rule_type', models.CharField(choices=[('weekly_limit', 'Лимит в неделю'), ('calm_consecutive', 'Ограничение спокойных подряд'), ('alternation', 'Чередование категорий')], max_length=32, verbose_name='Тип правила')),
                ('severity', models.CharField(choices=[('hard', 'Жесткое'), ('soft', 'Мягкое')], default='hard', max_length=10, verbose_name='Жесткость')),
                ('params_json', models.JSONField(blank=True, default=dict, verbose_name='Параметры (JSON)')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активно')),
                ('priority', models.PositiveIntegerField(default=100, verbose_name='Приоритет')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='distribution_rules_created', to=settings.AUTH_USER_MODEL, verbose_name='Создатель')),
            ],
            options={
                'verbose_name': 'Правило распределения',
                'verbose_name_plural': 'Правила распределения',
                'ordering': ['priority', 'id'],
            },
        ),
    ]
