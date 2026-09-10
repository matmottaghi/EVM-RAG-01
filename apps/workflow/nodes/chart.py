from __future__ import annotations

import json
import math
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ..errors import InvalidChartSpecError
from ..llm import invoke_json
from ..prompts import CHART_SYSTEM_PROMPT
from ..state import EVMSState
from .analyze import require_approved


class ChartSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chart_type: Literal["line", "bar", "scatter", "area", "histogram", "box", "heatmap"]
    x: str | None = None
    y: list[str] = Field(min_length=1, max_length=8)
    group_by: str | None = None
    title: str = Field(min_length=1, max_length=160)
    x_label: str | None = None
    y_label: str | None = None
    reference_lines: list[float] = Field(default_factory=list, max_length=8)

    @field_validator("reference_lines")
    @classmethod
    def finite_reference_lines(cls, values: list[float]) -> list[float]:
        if any(not math.isfinite(value) for value in values):
            raise ValueError("Reference lines must be finite.")
        return values


def validate_chart_spec(payload: dict[str, Any], columns: list[str]) -> ChartSpec:
    try:
        spec = ChartSpec.model_validate(payload)
    except ValidationError as exc:
        raise InvalidChartSpecError() from exc
    available = set(columns)
    requested = set(spec.y)
    if spec.x:
        requested.add(spec.x)
    if spec.group_by:
        requested.add(spec.group_by)
    if not requested.issubset(available):
        raise InvalidChartSpecError()
    if spec.chart_type in {"line", "bar", "scatter", "area"} and not spec.x:
        raise InvalidChartSpecError()
    return spec
def plan_chart(state: EVMSState) -> dict[str, Any]:
    rows = (state.get("rows") or [])[:50]
    context = {
        "question": state["user_prompt"],
        "analysis": state.get("analysis"),
        "columns": state.get("columns") or [],
        "approved_rows_sample": rows,
    }
    return invoke_json(
        CHART_SYSTEM_PROMPT,
        json.dumps(context, ensure_ascii=False, default=str),
    )


def generate_chart_spec(state: EVMSState) -> dict[str, object]:
    # A second independent gate prevents an unapproved dataset from reaching
    # the chart-planning LLM even if graph routing is changed later.
    require_approved(state)
    spec = validate_chart_spec(plan_chart(state), state.get("columns") or [])
    return {"chart_spec": spec.model_dump(mode="json"), "status": "rendering_chart"}


def _render_figure(frame: pd.DataFrame, spec: ChartSpec):
    import plotly.express as px

    color = spec.group_by if len(spec.y) == 1 else None
    common = {"data_frame": frame, "title": spec.title}
    if spec.chart_type == "line":
        return px.line(**common, x=spec.x, y=spec.y, color=color, markers=True)
    if spec.chart_type == "bar":
        return px.bar(**common, x=spec.x, y=spec.y, color=color, barmode="group")
    if spec.chart_type == "scatter":
        return px.scatter(**common, x=spec.x, y=spec.y[0], color=spec.group_by)
    if spec.chart_type == "area":
        return px.area(**common, x=spec.x, y=spec.y, color=color)
    if spec.chart_type == "histogram":
        return px.histogram(**common, x=spec.x or spec.y[0], color=spec.group_by)
    if spec.chart_type == "box":
        return px.box(**common, x=spec.x, y=spec.y[0], color=spec.group_by)
    numeric = frame[spec.y].apply(pd.to_numeric, errors="coerce")
    return px.imshow(numeric.corr(), text_auto=True, title=spec.title)
def render_chart(state: EVMSState) -> dict[str, object]:
    import plotly.io as pio

    require_approved(state)
    columns = state.get("columns") or []
    spec = validate_chart_spec(state.get("chart_spec") or {}, columns)
    frame = pd.DataFrame(state.get("rows") or [], columns=columns)
    try:
        figure = _render_figure(frame, spec)
        for value in spec.reference_lines:
            figure.add_hline(value=value, line_dash="dash", line_color="#ef8354")
        figure.update_layout(
            template="plotly_white",
            autosize=True,
            margin={"l": 48, "r": 24, "t": 64, "b": 48},
            xaxis_title=spec.x_label,
            yaxis_title=spec.y_label,
            legend_title_text=spec.group_by or "شاخص",
        )
        payload = json.loads(pio.to_json(figure, validate=True, pretty=False))
    except Exception as exc:
        raise InvalidChartSpecError() from exc
    return {"chart_payload": payload, "status": "completed"}
