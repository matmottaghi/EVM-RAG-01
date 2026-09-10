from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from django.conf import settings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .errors import LLMConfigurationError, LLMResponseError


def _validate_configuration() -> None:
    if not settings.LLM_BASE_URL or not settings.LLM_MODEL or not settings.LLM_API_KEY:
        raise LLMConfigurationError()


@lru_cache(maxsize=1)
def get_chat_model() -> ChatOpenAI:
    _validate_configuration()
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        temperature=settings.LLM_TEMPERATURE,
        timeout=settings.LLM_TIMEOUT_SECONDS,
        max_retries=1,
    )


def _content_as_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts)
    return str(content)


def invoke_text(system_prompt: str, user_prompt: str) -> str:
    try:
        response = get_chat_model().invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )
    except LLMConfigurationError:
        raise
    except Exception as exc:
        error = WorkflowLLMConnectionError()
        raise error from exc
    text = _content_as_text(response.content).strip()
    if not text:
        raise LLMResponseError()
    return text


class WorkflowLLMConnectionError(LLMResponseError):
    code = "llm_unavailable"
    public_message = "اتصال به مدل بارگذاری‌شده در LM Studio برقرار نشد."


def invoke_json(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    text = invoke_text(system_prompt, user_prompt)
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    start = text.find("{")
    if start < 0:
        raise LLMResponseError()
    try:
        value, _ = json.JSONDecoder().raw_decode(text[start:])
    except (json.JSONDecodeError, TypeError) as exc:
        raise LLMResponseError() from exc
    if not isinstance(value, dict):
        raise LLMResponseError()
    return value
