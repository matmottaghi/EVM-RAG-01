from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from time import perf_counter
from typing import Any

import pandas as pd
import pyodbc
from django.conf import settings
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

class DatabaseConfigurationError(RuntimeError):
    pass


class DatabaseExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    execution_duration_ms: int


def _connection_url() -> URL:
    if not settings.EVMS_DB_SERVER or not settings.EVMS_DB_DATABASE:
        raise DatabaseConfigurationError(
            "DB_SERVER and DB_DATABASE must be configured in .env."
        )

    query: dict[str, str] = {
        "driver": settings.EVMS_DB_DRIVER,
        "Encrypt": "yes" if settings.EVMS_DB_ENCRYPT else "no",
        "TrustServerCertificate": (
            "yes"
            if settings.EVMS_DB_TRUST_SERVER_CERTIFICATE
            else "no"
        ),
    }

    if settings.EVMS_DB_TRUSTED_CONNECTION:
        query["trusted_connection"] = "yes"
        username = None
        password = None

    else:
        if not settings.EVMS_DB_USERNAME or not settings.EVMS_DB_PASSWORD:
            raise DatabaseConfigurationError(
                "DB_USERNAME and DB_PASSWORD are required "
                "for SQL authentication."
            )

        username = settings.EVMS_DB_USERNAME
        password = settings.EVMS_DB_PASSWORD

    return URL.create(
        "mssql+pyodbc",
        username=username,
        password=password,
        host=settings.EVMS_DB_SERVER,
        database=settings.EVMS_DB_DATABASE,
        query=query,
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    engine = create_engine(
        _connection_url(),
        pool_pre_ping=True,
        future=True,
        connect_args={
            "timeout": settings.EVMS_DB_CONNECT_TIMEOUT_SECONDS
        },
        )

    # @event.listens_for(engine, "before_cursor_execute")
    # def set_query_timeout(
    #     _connection: Any,
    #     cursor: Any,
    #     _statement: str,
    #     _parameters: Any,
    #     _context: Any,
    #     _executemany: bool,
    # ) -> None:
    #     cursor.timeout = settings.EVMS_DB_QUERY_TIMEOUT_SECONDS

    return engine


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        converted = float(value)
        return converted if math.isfinite(converted) else None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except (TypeError, ValueError):
            pass
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def execute_query(sql: str) -> QueryResult:
    started = perf_counter()

    logger.info(
        "Executing EVMS SQL: %s",
        sql,
    )

    try:
        with get_engine().connect() as connection:
            frame = pd.read_sql_query(
                text(sql),
                connection
            )

    except (SQLAlchemyError, pyodbc.Error) as exc:
        print("=" * 80)
        print("EVMS SQL EXECUTION ERROR")
        print("SQL:")
        print(sql)
        print("ERROR:")
        print(repr(exc))
        print("=" * 80)

        raise DatabaseExecutionError(
            "The EVMS SQL Server query could not be completed."
        ) from exc

    columns = [
        str(column)
        for column in frame.columns
    ]

    rows = [
        {
            str(key): _json_safe(value)
            for key, value in record.items()
        }
        for record in frame.to_dict(
            orient="records"
        )
    ]

    return QueryResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        execution_duration_ms=round(
            (perf_counter() - started) * 1000
        ),
    )
