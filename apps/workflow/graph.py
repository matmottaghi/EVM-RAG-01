from __future__ import annotations

import os
import sqlite3
from functools import lru_cache
from typing import Any, Callable

from django.conf import settings
from langgraph.graph import END, START, StateGraph

from .nodes.analyze import analyze_data
from .nodes.chart import generate_chart_spec, render_chart
from .nodes.classify import classify_intent
from .nodes.confirm import route_confirmation, wait_for_confirmation
from .nodes.execute_sql import validate_and_execute_sql
from .nodes.generate_sql import generate_sql
from .state import EVMSState

Node = Callable[[EVMSState], dict[str, Any]]


@lru_cache(maxsize=1)
def get_checkpointer():
    os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
    from langgraph.checkpoint.sqlite import SqliteSaver

    path = settings.LANGGRAPH_CHECKPOINT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    return SqliteSaver(connection)


def build_graph(
    checkpointer: Any | None = None,
    node_overrides: dict[str, Node] | None = None,
):
    overrides = node_overrides or {}
    nodes: dict[str, Node] = {
        "classify_intent": classify_intent,
        "generate_sql": generate_sql,
        "validate_and_execute_sql": validate_and_execute_sql,
        "wait_for_confirmation": wait_for_confirmation,
        "analyze_data": analyze_data,
        "generate_chart_spec": generate_chart_spec,
        "render_chart": render_chart,
    }
    nodes.update(overrides)

    builder = StateGraph(EVMSState)
    for name, node in nodes.items():
        builder.add_node(name, node)
    builder.add_edge(START, "classify_intent")
    builder.add_edge("classify_intent", "generate_sql")
    builder.add_edge("generate_sql", "validate_and_execute_sql")
    builder.add_edge("validate_and_execute_sql", "wait_for_confirmation")
    builder.add_conditional_edges(
        "wait_for_confirmation",
        route_confirmation,
        {"approved": "analyze_data", "rejected": END},
    )
    builder.add_edge("analyze_data", "generate_chart_spec")
    builder.add_edge("generate_chart_spec", "render_chart")
    builder.add_edge("render_chart", END)
    return builder.compile(checkpointer=checkpointer or get_checkpointer())


@lru_cache(maxsize=1)
def get_graph():
    return build_graph()
