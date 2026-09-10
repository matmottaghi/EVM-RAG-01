from __future__ import annotations

import json
import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype

from apps.evms.glossary import get_relevant_glossary
from apps.evms.schema import get_relevant_schema


def dataframe_from_state(state: dict[str, Any]) -> pd.DataFrame:
    columns = [str(column) for column in state.get("columns") or []]
    return pd.DataFrame(state.get("rows") or [], columns=columns)


def _inferred_type(series: pd.Series) -> str:
    if is_datetime64_any_dtype(series):
        return "date"
    if is_numeric_dtype(series):
        return "number"
    return "string"


def build_column_metadata(frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Describe only returned columns; infer safe metadata for SQL aliases."""

    declared = get_relevant_schema(str(column) for column in frame.columns)
    result: dict[str, dict[str, Any]] = {}
    for raw_column in frame.columns:
        column = str(raw_column)
        metadata = dict(declared.get(column, {}))
        column_type = str(metadata.get("type") or _inferred_type(frame[raw_column]))
        metadata.setdefault("description", column)
        metadata["type"] = column_type
        metadata.setdefault(
            "role",
            "time" if column_type == "date" else "measure" if column_type == "number" else "dimension",
        )
        metadata["contains_nulls"] = bool(frame[raw_column].isna().any())
        result[column] = metadata
    return result


def _json_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        value = float(value)
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return round(value, 6) if math.isfinite(value) else None
    try:
        return None if pd.isna(value) else value
    except (TypeError, ValueError):
        return str(value)


def _actual_column(frame: pd.DataFrame, expected: str) -> str | None:
    return next(
        (str(column) for column in frame.columns if str(column).casefold() == expected.casefold()),
        None,
    )


def _reporting_period(
    frame: pd.DataFrame,
    metadata: dict[str, dict[str, Any]],
) -> tuple[dict[str, str], str | None, pd.Series | None]:
    time_column = next(
        (column for column, details in metadata.items() if details.get("role") == "time"),
        None,
    )
    if time_column is None:
        return {}, None, None
    parsed = pd.to_datetime(frame[time_column], errors="coerce")
    valid = parsed.dropna()
    if valid.empty:
        return {}, time_column, parsed
    start = _json_scalar(valid.min())
    end = _json_scalar(valid.max())
    return {
        "column": time_column,
        "start": start,
        "end": end,
        "latest": end,
    }, time_column, parsed


def _numeric_summary(
    frame: pd.DataFrame,
    metadata: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for column, details in metadata.items():
        if details.get("role") != "measure":
            continue
        numeric = pd.to_numeric(frame[column], errors="coerce")
        valid = numeric.dropna()
        if valid.empty:
            continue
        result[column] = {
            "count": int(valid.count()),
            "null_count": int(numeric.isna().sum()),
            "average": _json_scalar(valid.mean()),
            "minimum": _json_scalar(valid.min()),
            "maximum": _json_scalar(valid.max()),
        }
    return result


def _threshold_counts(frame: pd.DataFrame) -> dict[str, int]:
    rules = {"CPI": 1.0, "SPI": 1.0, "CV": 0.0, "SV": 0.0, "VAC": 0.0}
    result: dict[str, int] = {}
    for expected, threshold in rules.items():
        column = _actual_column(frame, expected)
        if column is None:
            continue
        numeric = pd.to_numeric(frame[column], errors="coerce")
        label = f"{expected}_below_1_count" if threshold == 1 else f"negative_{expected}_count"
        result[label] = int((numeric < threshold).sum())
    return result


def _project_details(
    frame: pd.DataFrame,
    metadata: dict[str, dict[str, Any]],
    time_column: str | None,
    parsed_dates: pd.Series | None,
) -> dict[str, Any]:
    project_column = _actual_column(frame, "ProjectCode") or _actual_column(frame, "ProjectName")
    if project_column is None:
        return {}
    project_count = int(frame[project_column].dropna().nunique())
    details: dict[str, Any] = {"project_column": project_column, "project_count": project_count}
    measures = [
        column
        for column, item in metadata.items()
        if item.get("role") == "measure"
    ]
    if not measures:
        return details

    if time_column and parsed_dates is not None and parsed_dates.notna().any():
        per_project = frame.copy()
        per_project["__reporting_date"] = parsed_dates
        per_project = (
            per_project.dropna(subset=[project_column, "__reporting_date"])
            .sort_values([project_column, "__reporting_date"], kind="mergesort")
            .groupby(project_column, sort=True, as_index=False)
            .tail(1)
        )
        basis = "latest_reporting_date_by_project"
    else:
        numeric = frame[[project_column, *measures]].copy()
        for column in measures:
            numeric[column] = pd.to_numeric(numeric[column], errors="coerce")
        per_project = numeric.groupby(project_column, sort=True, as_index=False).mean(numeric_only=True)
        basis = "average_by_project"

    if project_count <= 10:
        compact_columns = [project_column, *measures]
        details["values_by_project"] = [
            {column: _json_scalar(row[column]) for column in compact_columns}
            for _, row in per_project[compact_columns].iterrows()
        ]
        details["values_basis"] = basis

    worst: dict[str, list[dict[str, Any]]] = {}
    for metric_name in ("CPI", "SPI"):
        metric = _actual_column(per_project, metric_name)
        if metric is None:
            continue
        ranked = per_project.assign(
            __metric=pd.to_numeric(per_project[metric], errors="coerce")
        ).dropna(subset=["__metric"])
        ranked = ranked.sort_values(["__metric", project_column], kind="mergesort").head(5)
        worst[metric_name] = [
            {
                project_column: _json_scalar(row[project_column]),
                metric: _json_scalar(row[metric]),
            }
            for _, row in ranked.iterrows()
        ]
    if worst:
        details["worst_performing_projects"] = {"basis": basis, "metrics": worst}
    return details


def build_analysis_summary(frame: pd.DataFrame) -> dict[str, Any]:
    """Build a compact, deterministic summary without external information."""

    metadata = build_column_metadata(frame)
    period, time_column, parsed_dates = _reporting_period(frame, metadata)
    summary: dict[str, Any] = {
        "row_count": int(len(frame)),
        "reporting_period": period or None,
        "numeric_measures": _numeric_summary(frame, metadata),
        "performance_issue_counts": _threshold_counts(frame),
    }
    summary.update(_project_details(frame, metadata, time_column, parsed_dates))
    return summary


def build_analysis_prompt(question: str, frame: pd.DataFrame) -> str:
    context = {
        "user_question": question,
        "approved_result_columns": build_column_metadata(frame),
        "relevant_evms_glossary": get_relevant_glossary(frame.columns),
        "deterministic_summary": build_analysis_summary(frame),
    }
    return "Approved summarized analysis context (JSON):\n" + json.dumps(
        context,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def build_chart_prompt(question: str, frame: pd.DataFrame) -> str:
    context = {
        "user_question": question,
        "row_count": int(len(frame)),
        "available_approved_result_columns": build_column_metadata(frame),
        "relevant_evms_glossary": get_relevant_glossary(frame.columns),
    }
    return "Approved chart-planning metadata (JSON):\n" + json.dumps(
        context,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
