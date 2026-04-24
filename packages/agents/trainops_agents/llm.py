"""LLM abstraction layer — wraps LiteLLM so any provider works with one interface.
Supports: OpenAI, Anthropic, Google Gemini, Azure, Ollama, Cohere, and 100+
other providers transparently.
"""
from __future__ import annotations

import json
from typing import Any

import litellm
from litellm import acompletion

from trainops_tui.config import get_llm_api_key, get_llm_model

litellm.drop_params = True
litellm.set_verbose = False


async def chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    json_mode: bool = False,
) -> str:
    """Send a chat completion request. Returns assistant message content as a string."""
    _model = model or get_llm_model()
    _key = api_key or get_llm_api_key()

    kwargs: dict[str, Any] = {
        "model": _model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "api_key": _key,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = await acompletion(**kwargs)
    return resp.choices[0].message.content or ""


async def chat_json(
    messages: list[dict[str, str]],
    **kwargs: Any,
) -> dict[str, Any]:
    """chat() but parses and returns the JSON response."""
    raw = await chat(messages, json_mode=True, **kwargs)
    return json.loads(raw)  # type: ignore[no-any-return]


def build_system(role: str) -> dict[str, str]:
    return {"role": "system", "content": role}


def build_user(content: str) -> dict[str, str]:
    return {"role": "user", "content": content}


def build_assistant(content: str) -> dict[str, str]:
    return {"role": "assistant", "content": content}
