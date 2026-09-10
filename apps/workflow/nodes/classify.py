from __future__ import annotations

from ..state import EVMSState


def classify_intent(state: EVMSState) -> dict[str, str]:
    prompt = state["user_prompt"].casefold()
    groups = (
        ("forecast", ("forecast", "eac", "etc", "پیش‌بینی")),
        ("project_comparison", ("compare", "comparison", "مقایسه")),
        ("trend_analysis", ("trend", "روند", "ماه", "month")),
        ("cost_variance", ("cpi", "cost", "هزینه", "cv")),
        ("schedule_variance", ("spi", "schedule", "زمان", "برنامه", "sv")),
    )
    intent = next(
        (name for name, words in groups if any(word in prompt for word in words)),
        "project_performance",
    )
    return {"intent": intent, "status": "generating_sql"}
