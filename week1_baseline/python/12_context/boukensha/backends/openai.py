"""Port of ``lib/boukensha/backends/openai.rb``.

https://platform.openai.com/docs/api-reference/responses

gpt-5.x rejects ``reasoning_effort`` + tools on ``/v1/chat/completions``
("Please use /v1/responses"), so this backend targets the Responses API
instead of chat completions. That changes more than the URL: messages become
``input`` items, the system prompt becomes a top-level ``instructions``
string, tool defs are flat (no ``function:`` wrapper), and tool results
round-trip via ``function_call_output`` items matched by ``call_id`` rather
than a ``{"role": "tool"}`` message.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from boukensha.backends.base import Base
from boukensha.message import Message
from boukensha.tool import Tool

BASE_URL = "https://api.openai.com/v1/responses"


class OpenAI(Base):
    MODELS: ClassVar[dict[str, dict[str, Any]]] = {
        "gpt-5.5": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 5.0, "output": 30.0},
            "usage_unit": "tokens",
        },
        "gpt-5.4-mini": {
            "context_window": 400_000,
            "cost_per_million": {"input": 0.75, "output": 4.5},
            "usage_unit": "tokens",
        },
        "gpt-5.4-nano": {
            "context_window": 400_000,
            "cost_per_million": {"input": 0.2, "output": 1.25},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, *, api_key: str, model: str) -> None:
        super().__init__()
        self._api_key = api_key
        self._configure_model(model)

    def to_input(self, messages: list[Message]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "tool_result":
                items.append(
                    {"type": "function_call_output", "call_id": msg.tool_use_id, "output": str(msg.content)}
                )
            elif msg.role == "assistant":
                items.extend(self._assistant_items(msg.content))
            else:
                items.append({"role": msg.role, "content": msg.content})
        return items

    def to_tools(self, tools: dict[str, Tool]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": tool.parameters,
                    "required": list(tool.parameters.keys()),
                },
            }
            for tool in tools.values()
        ]

    def to_payload(
        self,
        context: Any,
        *,
        max_output_tokens: int = 1024,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "model": self.model,
            "instructions": context.system,
            "input": self.to_input(context.messages),
            "tools": self.to_tools(context.tools) if tools is None else tools,
            "max_output_tokens": max_output_tokens,
            "reasoning": {"effort": "none"},
        }

    # Normalizes a Responses API `output[]` array into the common shape (see
    # Backends.Base for the full content-block contract).
    def parse_response(self, response: dict[str, Any]) -> dict[str, Any]:
        function_calls: list[dict[str, Any]] = []
        content: list[dict[str, Any]] = []

        for item in response.get("output") or []:
            item_type = item.get("type")
            if item_type == "reasoning":
                text = "".join(s.get("text", "") for s in item.get("summary") or [])
                content.append({"type": "reasoning", "text": text})
            elif item_type == "message":
                text = "".join(
                    c.get("text", "") for c in item.get("content") or [] if c.get("type") == "output_text"
                )
                if text:
                    content.append({"type": "text", "text": text})
            elif item_type == "function_call":
                function_calls.append(item)

        for fc in function_calls:
            content.append(
                {
                    "type": "tool_use",
                    "id": fc.get("call_id"),
                    "name": fc.get("name"),
                    "input": json.loads(fc.get("arguments") or "{}"),
                }
            )

        return {
            "stop_reason": "end_turn" if not function_calls else "tool_use",
            "content": content,
        }

    def headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

    def url(self) -> str:
        return BASE_URL

    # ---------- internals ----------------------------------------------------

    # Rebuilds Responses input items from normalized content blocks (the
    # inverse of parse_response). Reasoning blocks are dropped — gpt-5.x
    # doesn't need them echoed back when reasoning effort is "none".
    @staticmethod
    def _assistant_items(content: str | list[dict[str, Any]]) -> list[dict[str, Any]]:
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content

        text = "".join(b["text"] for b in blocks if b["type"] == "text")
        items: list[dict[str, Any]] = [{"role": "assistant", "content": text}] if text else []

        for b in blocks:
            if b["type"] != "tool_use":
                continue
            items.append(
                {
                    "type": "function_call",
                    "call_id": b["id"],
                    "name": b["name"],
                    "arguments": json.dumps(b["input"]),
                }
            )
        return items
