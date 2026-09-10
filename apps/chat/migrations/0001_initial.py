# Generated manually for the initial EVMS Intelligence schema.

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ChatThread",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="ChatMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("user", "User"), ("assistant", "Assistant"), ("system", "System")], max_length=16)),
                ("content", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("thread", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="chat.chatthread")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.CreateModel(
            name="WorkflowRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("created", "Created"), ("generating_sql", "Generating SQL"), ("executing_sql", "Executing SQL"), ("waiting_for_confirmation", "Waiting for confirmation"), ("analyzing", "Analyzing"), ("completed", "Completed"), ("rejected", "Rejected"), ("failed", "Failed")], db_index=True, default="created", max_length=40)),
                ("user_prompt", models.TextField()),
                ("intent", models.CharField(blank=True, max_length=64)),
                ("generated_sql", models.TextField(blank=True)),
                ("sql_reason", models.TextField(blank=True)),
                ("confirmation_status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending", max_length=16)),
                ("analysis", models.TextField(blank=True)),
                ("chart_spec", models.JSONField(blank=True, null=True)),
                ("chart_payload", models.JSONField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("execution_duration_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("thread", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="workflow_runs", to="chat.chatthread")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="DatasetSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("columns_json", models.JSONField(default=list)),
                ("rows_json", models.JSONField(default=list)),
                ("row_count", models.PositiveIntegerField(default=0)),
                ("approved", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("workflow_run", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="dataset_snapshot", to="chat.workflowrun")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="chatmessage",
            index=models.Index(fields=["thread", "created_at"], name="chat_chatme_thread__b4c881_idx"),
        ),
        migrations.AddIndex(
            model_name="workflowrun",
            index=models.Index(fields=["thread", "created_at"], name="chat_workfl_thread__ebf759_idx"),
        ),
        migrations.AddIndex(
            model_name="workflowrun",
            index=models.Index(fields=["confirmation_status", "status"], name="chat_workfl_confirm_0c4bd0_idx"),
        ),
    ]
