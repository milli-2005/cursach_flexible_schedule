from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_chat_groups_and_reads'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ChatConversationPin',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Закреплено в')),
                ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pins', to='core.chatconversation', verbose_name='Диалог')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_pins', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Закрепленный диалог',
                'verbose_name_plural': 'Закрепленные диалоги',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='chatconversationpin',
            constraint=models.UniqueConstraint(fields=('user', 'conversation'), name='unique_chat_conversation_pin'),
        ),
    ]
