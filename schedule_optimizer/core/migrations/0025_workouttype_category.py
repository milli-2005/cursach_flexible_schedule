from django.db import migrations, models


def fill_workout_categories(apps, schema_editor):
    WorkoutType = apps.get_model('core', 'WorkoutType')

    def infer(name: str) -> str:
        n = (name or '').lower()
        if any(x in n for x in ['dance', 'танц', 'lady dance', 'bachata', 'восточн', 'стрип']):
            return 'dance'
        if any(x in n for x in ['кардио', 'cardio', 'hiit', 'табата', 'tabata', 'body flex']):
            return 'cardio'
        if any(x in n for x in ['сил', 'strength', 'power', 'подкач']):
            return 'strength'
        if any(x in n for x in ['stretch', 'растяж', 'йога', 'йог', 'здоров', 'пилатес', 'pilates', 'spine']):
            return 'calm'
        return 'other'

    for wt in WorkoutType.objects.all():
        wt.category = infer(wt.name)
        wt.save(update_fields=['category'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_schedule_versions'),
    ]

    operations = [
        migrations.AddField(
            model_name='workouttype',
            name='category',
            field=models.CharField(choices=[('calm', 'Спокойные'), ('cardio', 'Кардио'), ('strength', 'Силовые'), ('dance', 'Танцы'), ('other', 'Другое')], default='other', max_length=20, verbose_name='Категория занятия'),
        ),
        migrations.RunPython(fill_workout_categories, migrations.RunPython.noop),
    ]

