from django.contrib import admin

from .models import ChatMessage, ChatThread, DatasetSnapshot, WorkflowRun


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "updated_at")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("content",)


@admin.register(WorkflowRun)
class WorkflowRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "thread",
        "status",
        "confirmation_status",
        "created_at",
    )
    list_filter = ("status", "confirmation_status")
    search_fields = ("user_prompt", "generated_sql", "analysis")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(DatasetSnapshot)
class DatasetSnapshotAdmin(admin.ModelAdmin):
    list_display = ("workflow_run", "row_count", "approved", "created_at")
    list_filter = ("approved",)
