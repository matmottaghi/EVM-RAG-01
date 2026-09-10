from __future__ import annotations

from django.conf import settings

from apps.evms.repository import execute_query
from apps.evms.sql_validator import validate_sql

from ..errors import EmptyDatasetError
from ..state import EVMSState


def validate_and_execute_sql(state: EVMSState) -> dict[str, object]:
    validated = validate_sql(
        state.get("generated_sql") or "",
        max_rows=settings.EVMS_DB_MAX_ROWS,
        allowed_schemas=settings.EVMS_DB_ALLOWED_SCHEMAS,
    )
    result = execute_query(validated.sql)
    if result.row_count == 0:
        raise EmptyDatasetError()
    return {
        "generated_sql": validated.sql,
        "columns": result.columns,
        "rows": result.rows,
        "row_count": result.row_count,
        "execution_duration_ms": result.execution_duration_ms,
        "confirmation_status": "pending",
        "status": "waiting_for_confirmation",
    }
