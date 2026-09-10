from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("chat", "0001_initial")]

    operations = [
        migrations.AddConstraint(
            model_name="workflowrun",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("confirmation_status", "pending"),
                    ("status", "waiting_for_confirmation"),
                ),
                fields=("thread",),
                name="one_pending_run_per_thread",
            ),
        )
    ]
