from __future__ import annotations

import uuid

from django.db import models


class ChatThread(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return str(self.id)


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    thread = models.ForeignKey(
        ChatThread,
        related_name="messages",
        on_delete=models.CASCADE,
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["thread", "created_at"])]


class WorkflowRun(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        GENERATING_SQL = "generating_sql", "Generating SQL"
        EXECUTING_SQL = "executing_sql", "Executing SQL"
        WAITING = "waiting_for_confirmation", "Waiting for confirmation"
        ANALYZING = "analyzing", "Analyzing"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Failed"

    class Confirmation(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(
        ChatThread,
        related_name="workflow_runs",
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.CREATED,
        db_index=True,
    )
    user_prompt = models.TextField()
    intent = models.CharField(max_length=64, blank=True)
    generated_sql = models.TextField(blank=True)
    sql_reason = models.TextField(blank=True)
    confirmation_status = models.CharField(
        max_length=16,
        choices=Confirmation.choices,
        default=Confirmation.PENDING,
    )
    analysis = models.TextField(blank=True)
    chart_spec = models.JSONField(null=True, blank=True)
    chart_payload = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    execution_duration_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["thread", "created_at"]),
            models.Index(fields=["confirmation_status", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["thread"],
                condition=models.Q(
                    status="waiting_for_confirmation",
                    confirmation_status="pending",
                ),
                name="one_pending_run_per_thread",
            )
        ]


class DatasetSnapshot(models.Model):
    workflow_run = models.OneToOneField(
        WorkflowRun,
        related_name="dataset_snapshot",
        on_delete=models.CASCADE,
    )
    columns_json = models.JSONField(default=list)
    rows_json = models.JSONField(default=list)
    row_count = models.PositiveIntegerField(default=0)
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
