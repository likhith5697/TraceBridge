"""The only place this process knows an LLM API key or a provider's native
request/response wire format. investigator.py, evidence.py, and report.py
only ever see the provider-agnostic ToolCall/AssistantTurn/ToolResult types
below - swapping providers means changing this file (and config.py) only.

History is a list of tuples so it stays trivially provider-agnostic:
  ("user", "some text")
  ("assistant", AssistantTurn(...))
  ("tool_results", [ToolResult(...), ...])   # all results for the
                                              # immediately preceding
                                              # assistant turn's tool calls
"""

import json
from dataclasses import dataclass
from typing import Any, Protocol

from tracebridge_investigator.config import Config
from tracebridge_investigator.mcp_client import ToolSpec

_MAX_TOKENS = 2048


class LLMError(RuntimeError):
    """The LLM call failed outright: no key, timeout, rate limit, provider error."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class AssistantTurn:
    text: str | None
    tool_calls: list[ToolCall]


@dataclass(frozen=True)
class ToolResult:
    tool_call_id: str
    content: str
    is_error: bool


HistoryEntry = tuple[str, Any]


class LLMClient(Protocol):
    def send(self, system: str, history: list[HistoryEntry], tool_specs: list[ToolSpec]) -> AssistantTurn: ...


def build_llm_client(config: Config) -> LLMClient:
    if config.llm_provider == "anthropic":
        return AnthropicLLMClient(config)
    if config.llm_provider == "openai":
        return OpenAILLMClient(config)
    raise LLMError(f"unsupported LLM_PROVIDER: {config.llm_provider!r}")


class AnthropicLLMClient:
    def __init__(self, config: Config):
        import anthropic

        if not config.anthropic_api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        self._anthropic = anthropic
        self._model = config.llm_model
        self._client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    def send(self, system: str, history: list[HistoryEntry], tool_specs: list[ToolSpec]) -> AssistantTurn:
        messages = _history_to_anthropic(history)
        tools = [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in tool_specs]
        try:
            response = self._client.messages.create(
                model=self._model, max_tokens=_MAX_TOKENS, system=system, messages=messages, tools=tools
            )
        except self._anthropic.APIError as exc:
            raise LLMError(f"LLM call failed: {exc}") from exc

        text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), None)
        tool_calls = [
            ToolCall(b.id, b.name, b.input) for b in response.content if getattr(b, "type", None) == "tool_use"
        ]
        return AssistantTurn(text=text, tool_calls=tool_calls)


class OpenAILLMClient:
    def __init__(self, config: Config):
        import openai

        if not config.openai_api_key:
            raise LLMError("OPENAI_API_KEY is not set")
        self._openai = openai
        self._model = config.llm_model
        self._client = openai.OpenAI(api_key=config.openai_api_key)

    def send(self, system: str, history: list[HistoryEntry], tool_specs: list[ToolSpec]) -> AssistantTurn:
        messages = [{"role": "system", "content": system}] + _history_to_openai(history)
        tools = [
            {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.input_schema}}
            for t in tool_specs
        ]
        try:
            response = self._client.chat.completions.create(model=self._model, messages=messages, tools=tools)
        except self._openai.APIError as exc:
            raise LLMError(f"LLM call failed: {exc}") from exc

        choice = response.choices[0].message
        tool_calls = [
            ToolCall(tc.id, tc.function.name, json.loads(tc.function.arguments))
            for tc in (choice.tool_calls or [])
        ]
        return AssistantTurn(text=choice.content, tool_calls=tool_calls)


def _history_to_anthropic(history: list[HistoryEntry]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for kind, payload in history:
        if kind == "user":
            messages.append({"role": "user", "content": payload})
        elif kind == "assistant":
            turn: AssistantTurn = payload
            blocks: list[dict[str, Any]] = []
            if turn.text:
                blocks.append({"type": "text", "text": turn.text})
            for tc in turn.tool_calls:
                blocks.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments})
            messages.append({"role": "assistant", "content": blocks})
        elif kind == "tool_results":
            results: list[ToolResult] = payload
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": r.tool_call_id,
                            "content": r.content,
                            "is_error": r.is_error,
                        }
                        for r in results
                    ],
                }
            )
    return messages


def _history_to_openai(history: list[HistoryEntry]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for kind, payload in history:
        if kind == "user":
            messages.append({"role": "user", "content": payload})
        elif kind == "assistant":
            turn: AssistantTurn = payload
            message: dict[str, Any] = {"role": "assistant", "content": turn.text}
            if turn.tool_calls:
                message["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in turn.tool_calls
                ]
            messages.append(message)
        elif kind == "tool_results":
            results: list[ToolResult] = payload
            for r in results:
                content = f"ERROR: {r.content}" if r.is_error else r.content
                messages.append({"role": "tool", "tool_call_id": r.tool_call_id, "content": content})
    return messages
