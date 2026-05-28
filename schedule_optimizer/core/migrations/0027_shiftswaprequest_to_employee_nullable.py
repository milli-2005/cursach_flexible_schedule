from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_alter_distributionrule_rule_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='shiftswaprequest',
            name='to_employee',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='swap_requests_received',
                to='core.employee',
            ),
        ),
    ]

