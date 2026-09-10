from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from langgraph.types import Command

from apps.evms.repository import DatabaseConfigurationError, DatabaseExecutionError
from apps.evms.sql_validator import SQLValidationError
from apps.workflow.errors import (
    CheckpointMissingError,
    InvalidWorkflowTransition,
    WorkflowError,
)
from apps.workflow.graph import get_graph

from .models import ChatMessage, DatasetSnapshot, WorkflowRun

logger = logging.getLogger(__name__)


def graph_config(run: WorkflowRun) -> dict[str, dict[str, str]]:
    # A workflow run, rather than the conversation, is the LangGraph thread.
    # This prevents a later query from accidentally resuming an older run.
    return {"configurable": {"thread_id": str(run.id)}}


def public_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, WorkflowError):
        return exc.code, exc.public_message
    if isinstance(exc, SQLValidationError):
        return "invalid_sql", "پرس‌وجوی تولیدشده با سیاست دسترسی فقط‌خواندنی سازگار نبود."
    if isinstance(exc, DatabaseConfigurationError):
        return "database_configuration_error", "تنظیمات اتصال SQL Server در فایل .env کامل نیست."
    if isinstance(exc, DatabaseExecutionError):
        return "database_unavailable", "اتصال یا اجرای پرس‌وجو روی SQL Server ناموفق بود."
    return "workflow_error", "اجرای گردش‌کار با خطای کنترل‌نشده متوقف شد."


def _record_failure(run: WorkflowRun, exc: Exception) -> WorkflowRun:
    code, message = public_error(exc)
    logger.exception("workflow_failed run_id=%s code=%s", run.id, code)
    run.status = WorkflowRun.Status.FAILED
    run.error_message = message
    run.save(update_fields=["status", "error_message", "updated_at"])
    ChatMessage.objects.create(thread=run.thread, role=ChatMessage.Role.SYSTEM, content=message)
    return run


def _persist_graph_state(run: WorkflowRun, state: dict[str, Any]) -> WorkflowRun:
    scalar_fields = (
        "intent", "generated_sql", "sql_reason", "confirmation_status",
        "analysis", "chart_spec", "chart_payload", "execution_duration_ms", "status",
    )
    changed: list[str] = []
    for field in scalar_fields:
        if field in state and state[field] is not None:
            setattr(run, field, state[field])
            changed.append(field)
    run.error_message = state.get("error") or ""
    changed.extend(["error_message", "updated_at"])
    run.save(update_fields=list(dict.fromkeys(changed)))

    if state.get("columns") is not None and state.get("rows") is not None:
        DatasetSnapshot.objects.update_or_create(
            workflow_run=run,
            defaults={
                "columns_json": state["columns"],
                "rows_json": state["rows"],
                "row_count": state.get("row_count") or 0,
                "approved": state.get("confirmation_status") == "approved",
            },
        )
    return run


def start_workflow(
    run: WorkflowRun,
    *,
    correction_context: str | None = None,
) -> WorkflowRun:
    initial_state = {
        "run_id": str(run.id),
        "thread_id": str(run.thread_id),
        "user_prompt": run.user_prompt,
        "correction_context": correction_context,
        "confirmation_status": "pending",
        "status": "created",
    }
    logger.info(
        "workflow_started run_id=%s thread_id=%s prompt=%r",
        run.id,
        run.thread_id,
        run.user_prompt,
    )
    try:
        result = get_graph().invoke(initial_state, config=graph_config(run))
        _persist_graph_state(run, result)
    except Exception as exc:
        return _record_failure(run, exc)

    logger.info(
        "dataset_ready run_id=%s sql=%r rows=%s duration_ms=%s",
        run.id,
        run.generated_sql,
        getattr(run.dataset_snapshot, "row_count", 0),
        run.execution_duration_ms,
    )
    ChatMessage.objects.create(
        thread=run.thread,
        role=ChatMessage.Role.SYSTEM,
        content="داده بازیابی شد؛ پیش از تحلیل آن را تأیید یا رد کنید.",
    )
    return run


def _ensure_checkpoint(run: WorkflowRun) -> None:
    snapshot = get_graph().get_state(graph_config(run))
    if not snapshot.values or "wait_for_confirmation" not in snapshot.next:
        raise CheckpointMissingError()


def _lock_for_decision(run: WorkflowRun, action: str) -> WorkflowRun:
    with transaction.atomic():
        locked = WorkflowRun.objects.select_for_update().get(pk=run.pk)
        if (
            locked.status != WorkflowRun.Status.WAITING
            or locked.confirmation_status != WorkflowRun.Confirmation.PENDING
        ):
            raise InvalidWorkflowTransition()
        locked.confirmation_status = action
        locked.status = (
            WorkflowRun.Status.ANALYZING
            if action == WorkflowRun.Confirmation.APPROVED
            else WorkflowRun.Status.REJECTED
        )
        locked.save(update_fields=["confirmation_status", "status", "updated_at"])
        DatasetSnapshot.objects.filter(workflow_run=locked).update(
            approved=action == WorkflowRun.Confirmation.APPROVED
        )
    return locked


def approve_workflow(run: WorkflowRun) -> WorkflowRun:
    try:
        _ensure_checkpoint(run)
        run = _lock_for_decision(run, WorkflowRun.Confirmation.APPROVED)
        logger.info("dataset_approved run_id=%s thread_id=%s", run.id, run.thread_id)
        result = get_graph().invoke(
            Command(resume={"action": "approved"}),
            config=graph_config(run),
        )
        _persist_graph_state(run, result)
    except (CheckpointMissingError, InvalidWorkflowTransition):
        raise
    except Exception as exc:
        return _record_failure(run, exc)

    ChatMessage.objects.create(
        thread=run.thread,
        role=ChatMessage.Role.ASSISTANT,
        content=run.analysis,
    )
    logger.info(
        "workflow_completed run_id=%s chart_spec=%s",
        run.id,
        run.chart_spec,
    )
    return run


def reject_workflow(run: WorkflowRun, *, reason: str = "") -> WorkflowRun:
    try:
        _ensure_checkpoint(run)
        run = _lock_for_decision(run, WorkflowRun.Confirmation.REJECTED)
        result = get_graph().invoke(
            Command(resume={"action": "rejected", "reason": reason}),
            config=graph_config(run),
        )
        _persist_graph_state(run, result)
    except (CheckpointMissingError, InvalidWorkflowTransition):
        raise
    except Exception as exc:
        return _record_failure(run, exc)
    message = "داده رد شد. لطفاً اشکال داده یا فیلتر موردنظر را در پیام بعدی توضیح دهید."
    if reason:
        message += f" دلیل ثبت‌شده: {reason}"
    ChatMessage.objects.create(
        thread=run.thread,
        role=ChatMessage.Role.SYSTEM,
        content=message,
    )
    logger.info("dataset_rejected run_id=%s reason=%r", run.id, reason)
    return run
