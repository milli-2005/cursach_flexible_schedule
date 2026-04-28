from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_alter_availability_options_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='chatconversation',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='chat_groups_created',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Создатель группы',
            ),
        ),
        migrations.AlterField(
            model_name='chatmessage',
            name='text',
            field=models.TextField(blank=True, default='', verbose_name='Текст сообщения'),
        ),
        migrations.CreateModel(
            name='ChatMessageAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='chat_files/%Y/%m/%d/', verbose_name='Файл')),
                ('original_name', models.CharField(max_length=255, verbose_name='Имя файла')),
                ('size', models.PositiveIntegerField(default=0, verbose_name='Размер (байт)')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True, verbose_name='Загружен')),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='core.chatmessage', verbose_name='Сообщение')),
            ],
            options={
                'verbose_name': 'Вложение сообщения',
                'verbose_name_plural': 'Вложения сообщений',
                'ordering': ['id'],
            },
        ),
    ]
