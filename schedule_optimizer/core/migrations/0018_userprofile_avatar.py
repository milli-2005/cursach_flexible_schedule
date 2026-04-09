from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_chat_conversation_pins'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='avatar',
            field=models.ImageField(blank=True, null=True, upload_to='avatars/', verbose_name='Аватар'),
        ),
    ]
