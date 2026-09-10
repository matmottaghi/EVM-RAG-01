from __future__ import annotations

import logging

from django.conf import settings

from apps.evms.repository import execute_query
from apps.evms.sql_validator import validate_sql

from ..errors import EmptyDatasetError
from ..state import EVMSState

logger = logging.getLogger(__name__)


def validate_and_execute_sql(state: EVMSState) -> dict[str, object]:
    generated_sql = state.get("generated_sql") or ""
    logger.info("SQL_VALIDATION_START sql=%s", generated_sql)
    try:
        validated = validate_sql(
            generated_sql,
            max_rows=settings.EVMS_DB_MAX_ROWS,
            allowed_schemas=settings.EVMS_DB_ALLOWED_SCHEMAS,
        )
    except Exception as exc:
        logger.exception(
            "SQL_VALIDATION_FAILURE exception_type=%s",
            type(exc).__name__,
        )
        raise
    logger.info("VALIDATED_SQL sql=%s", validated.sql)
    logger.info("REFERENCED_RELATIONS relations=%s", list(validated.tables))
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
