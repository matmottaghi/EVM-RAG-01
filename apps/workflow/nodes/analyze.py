from __future__ import annotations

import json

from django.conf import settings

from apps.evms.glossary import glossary_text

from ..errors import UnapprovedDataError
from ..llm import invoke_text
from ..prompts import ANALYSIS_SYSTEM_PROMPT
from ..state import EVMSState


def require_approved(state: EVMSState) -> None:
    if state.get("confirmation_status") != "approved":
        raise UnapprovedDataError()


def analyze_confirmed_dataset(state: EVMSState) -> str:
    row_count = int(state.get("row_count") or 0)
    max_rows = max(1, settings.LLM_MAX_DATA_ROWS)
    rows = (state.get("rows") or [])[:max_rows]
    dataset = {
        "columns": state.get("columns") or [],
        "row_count": row_count,
        "rows_supplied": len(rows),
        "rows": rows,
    }
    prompt = (
        f"Original question:\n{state['user_prompt']}\n\n"
        f"EVMS glossary:\n{glossary_text()}\n\n"
        "Approved dataset (JSON):\n"
        f"{json.dumps(dataset, ensure_ascii=False, default=str)}"
    )
    return invoke_text(ANALYSIS_SYSTEM_PROMPT, prompt)


def analyze_data(state: EVMSState) -> dict[str, str]:
    # This code-level gate is deliberately placed before any dataset formatting
    # or LLM invocation. Pending/rejected rows cannot reach the analysis model.
    require_approved(state)
    return {"analysis": analyze_confirmed_dataset(state), "status": "generating_chart"}
