from __future__ import annotations

from langgraph.types import interrupt

from ..errors import InvalidWorkflowTransition
from ..state import EVMSState


def wait_for_confirmation(state: EVMSState) -> dict[str, str]:
    decision = interrupt(
        {
            "type": "dataset_confirmation",
            "run_id": state["run_id"],
            "row_count": state.get("row_count", 0),
            "columns": state.get("columns", []),
            "message": "آیا داده بازیابی‌شده صحیح است؟",
        }
    )
    if not isinstance(decision, dict):
        raise InvalidWorkflowTransition()
    action = decision.get("action")
    if action == "approved":
        return {"confirmation_status": "approved", "status": "analyzing"}
    if action == "rejected":
        return {"confirmation_status": "rejected", "status": "rejected"}
    raise InvalidWorkflowTransition()


def route_confirmation(state: EVMSState) -> str:
    return "approved" if state.get("confirmation_status") == "approved" else "rejected"
