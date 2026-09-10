from __future__ import annotations

from typing import Any, TypedDict


class EVMSState(TypedDict, total=False):
    run_id: str
    thread_id: str
    user_prompt: str
    correction_context: str | None
    intent: str | None
    generated_sql: str | None
    sql_reason: str | None
    columns: list[str] | None
    rows: list[dict[str, Any]] | None
    row_count: int | None
    execution_duration_ms: int | None
    confirmation_status: str | None
    status: str
    analysis: str | None
    chart_spec: dict[str, Any] | None
    chart_payload: dict[str, Any] | None
    error: str | None
