from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q
from django.utils import timezone


def seed_chat_participants_and_read_states(apps, schema_editor):
    ChatConversation = apps.get_model('core', 'ChatConversation')
    ChatMessage = apps.get_model('core', 'ChatMessage')
    ChatMessageRead = apps.get_model('core', 'ChatMessageRead')

    for conv in ChatConversation.objects.all():
        # Для старых личных диалогов наполняем M2M участников.
        user_ids = []
        if conv.participant_a_id:
            user_ids.append(conv.participant_a_id)
        if conv.participant_b_id and conv.participant_b_id not in user_ids:
            user_ids.append(conv.participant_b_id)
        if user_ids:
            conv.participants.add(*user_ids)

    # Для существующих сообщений создаем статусы прочтения для всех участников, кроме отправителя.
    # Ставим read_at сразу, чтобы не было "ложной лавины" непрочитанных старых сообщений.
    for msg in ChatMessage.objects.select_related('conversation', 'sender').all():
        participant_ids = list(msg.conversation.participants.values_list('id', flat=True))
        for uid in participant_ids:
            if uid == msg.sender_id:
                continue
            ChatMessageRead.objects.get_or_create(
                message_id=msg.id,
                user_id=uid,
                defaults={'read_at': timezone.now()},
            )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_chat_models'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='chatconversation',
            name='participant_a',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='chat_conversations_as_a', to=settings.AUTH_USER_MODEL, verbose_name='Участник A'),
        ),
        migrations.AlterField(
            model_name='chatconversation',
            name='participant_b',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='chat_conversations_as_b', to=settings.AUTH_USER_MODEL, verbose_name='Участник B'),
        ),
        migrations.AddField(
            model_name='chatconversation',
            name='is_group',
            field=models.BooleanField(default=False, verbose_name='Групповой чат'),
        ),
        migrations.AddField(
            model_name='chatconversation',
            name='participants',
            field=models.ManyToManyField(blank=True, related_name='chat_conversations', to=settings.AUTH_USER_MODEL, verbose_name='Участники'),
        ),
        migrations.AddField(
            model_name='chatconversation',
            name='title',
            field=models.CharField(blank=True, max_length=200, verbose_name='Название группы'),
        ),
        migrations.CreateModel(
            name='ChatMessageRead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('read_at', models.DateTimeField(blank=True, null=True, verbose_name='Прочитано в')),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='read_states', to='core.chatmessage', verbose_name='Сообщение')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_message_read_states', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Статус прочтения сообщения',
                'verbose_name_plural': 'Статусы прочтения сообщений',
            },
        ),
        migrations.RemoveConstraint(
            model_name='chatconversation',
            name='unique_chat_conversation_pair',
        ),
        migrations.AddConstraint(
            model_name='chatconversation',
            constraint=models.UniqueConstraint(
                condition=Q(is_group=False, participant_a__isnull=False, participant_b__isnull=False),
                fields=('participant_a', 'participant_b'),
                name='unique_chat_conversation_pair'
            ),
        ),
        migrations.AddConstraint(
            model_name='chatmessageread',
            constraint=models.UniqueConstraint(fields=('message', 'user'), name='unique_message_read_state'),
        ),
        migrations.RunPython(seed_chat_participants_and_read_states, migrations.RunPython.noop),
    ]
