from __future__ import annotations

from apps.evms.glossary import glossary_text
from apps.evms.schema import semantic_schema_text

from ..errors import LLMResponseError
from ..llm import invoke_json
from ..prompts import SQL_SYSTEM_PROMPT
from ..state import EVMSState


def generate_sql_plan(
    question: str,
    intent: str,
    correction_context: str | None,
) -> dict[str, str]:
    prompt = (
        f"User question:\n{question}\n\nIntent: {intent}\n\n"
        f"Semantic schema:\n{semantic_schema_text()}\n\n"
        f"EVMS glossary:\n{glossary_text()}"
    )
    if correction_context:
        prompt += f"\n\nPreviously rejected request/context:\n{correction_context}"
    result = invoke_json(SQL_SYSTEM_PROMPT, prompt)
    sql = result.get("sql")
    reason = result.get("reason", "")
    if not isinstance(sql, str) or not sql.strip() or not isinstance(reason, str):
        raise LLMResponseError()
    return {"sql": sql.strip(), "reason": reason.strip()}


def generate_sql(state: EVMSState) -> dict[str, str]:
    plan = generate_sql_plan(
        state["user_prompt"],
        state.get("intent") or "project_performance",
        state.get("correction_context"),
    )
    return {
        "generated_sql": plan["sql"],
        "sql_reason": plan["reason"],
        "status": "executing_sql",
    }
