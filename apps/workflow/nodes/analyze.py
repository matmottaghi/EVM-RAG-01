from __future__ import annotations

import logging

from ..context import (
    build_analysis_prompt,
    build_analysis_summary,
    dataframe_from_state,
)
from ..errors import UnapprovedDataError
from ..llm import invoke_text
from ..prompts import ANALYSIS_SYSTEM_PROMPT
from ..state import EVMSState

logger = logging.getLogger(__name__)


def require_approved(state: EVMSState) -> None:
    if state.get("confirmation_status") != "approved":
        raise UnapprovedDataError()


def analyze_confirmed_dataset(state: EVMSState) -> str:
    require_approved(state)
    frame = dataframe_from_state(state)
    summary = build_analysis_summary(frame)
    logger.info(
        "ANALYSIS_SUMMARY row_count=%s columns=%s summary=%s",
        len(frame),
        [str(column) for column in frame.columns],
        summary,
    )
    prompt = build_analysis_prompt(state["user_prompt"], frame)
    return invoke_text(
        ANALYSIS_SYSTEM_PROMPT,
        prompt,
        log_prefix="ANALYSIS",
    )


def analyze_data(state: EVMSState) -> dict[str, str]:
    # This code-level gate is deliberately placed before any dataset formatting
    # or LLM invocation. Pending/rejected rows cannot reach the analysis model.
    require_approved(state)
    return {"analysis": analyze_confirmed_dataset(state), "status": "generating_chart"}
