"""Mammouth AI backend — OpenAI-compatible.

Mammouth (https://mammouth.ai) exposes an OpenAI-compatible Chat Completions
API, so this backend mirrors ``openai.py`` exactly except for its base URL, its
model table, and the payload's token-limit field (``max_tokens``, per Mammouth's
API docs) instead of OpenAI's newer ``max_completion_tokens``.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from boukensha.backends.base import Base
from boukensha.message import Message
from boukensha.tool import Tool

BASE_URL = "https://api.mammouth.ai/v1/chat/completions"


class Mammouth(Base):
    MODELS: ClassVar[dict[str, dict[str, Any]]] = {
        "claude-sonnet-5": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 2.0, "output": 10.0},
            "usage_unit": "tokens",
        },
        "claude-opus-4-8": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 5.0, "output": 25.0},
            "usage_unit": "tokens",
        },
        "gpt-5.5": {
            "context_window": 1_050_000,
            "cost_per_million": {"input": 5.0, "output": 30.0},
            "usage_unit": "tokens",
        },
        "gpt-5.4": {
            "context_window": 922_000,
            "cost_per_million": {"input": 2.5, "output": 15.0},
            "usage_unit": "tokens",
        },
        "gemini-3.5-flash": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 1.5, "output": 9.0},
            "usage_unit": "tokens",
        },
        "gemini-2.5-pro": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 2.5, "output": 15.0},
            "usage_unit": "tokens",
        },
        "mistral-large-3": {
            "context_window": 262_144,
            "cost_per_million": {"input": 0.5, "output": 1.5},
            "usage_unit": "tokens",
        },
        "grok-4.5": {
            "context_window": 500_000,
            "cost_per_million": {"input": 2.0, "output": 6.0},
            "usage_unit": "tokens",
        },
        "deepseek-v4-pro": {
            "context_window": 1_050_000,
            "cost_per_million": {"input": 1.74, "output": 3.48},
            "usage_unit": "tokens",
        },
        "qwen3.7-max": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 2.5, "output": 7.5},
            "usage_unit": "tokens",
        },
        "kimi-k3": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 3.0, "output": 15.0},
            "usage_unit": "tokens",
        },
        "mammouth-recommended": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 1.4, "output": 4.4},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, *, api_key: str, model: str) -> None:
        super().__init__()
        self._api_key = api_key
        self._configure_model(model)

    def to_messages(self, system: str | None, messages: list[Message]) -> list[dict[str, Any]]:
        system_message = [{"role": "system", "content": system}]
        conversation = []
        for msg in messages:
            if msg.role == "tool_result":
                conversation.append(
                    {"role": "tool", "tool_call_id": msg.tool_use_id, "content": msg.content}
                )
            elif msg.role == "assistant":
                conversation.append(self._assistant_message(msg.content))
            else:
                conversation.append({"role": msg.role, "content": msg.content})
        return system_message + conversation

    def to_tools(self, tools: dict[str, Tool]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": list(tool.parameters.keys()),
                    },
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
            "messages": self.to_messages(context.system, context.messages),
            "tools": self.to_tools(context.tools) if tools is None else tools,
            "max_tokens": max_output_tokens,
        }

    # Normalizes an OpenAI-compatible chat completions response into the common
    # shape:
    #   {stop_reason: "tool_use" | "end_turn", content: [ {"type": "text", "text": ...} |
    #    {"type": "tool_use", "id": ..., "name": ..., "input": ...} ]}
    def parse_response(self, response: dict[str, Any]) -> dict[str, Any]:
        message = (response.get("choices") or [{}])[0].get("message") or {}
        tool_calls = message.get("tool_calls") or []

        content: list[dict[str, Any]] = []
        if message.get("content"):
            content.append({"type": "text", "text": message["content"]})

        for tc in tool_calls:
            function = tc.get("function") or {}
            content.append(
                {
                    "type": "tool_use",
                    "id": tc.get("id"),
                    "name": function.get("name"),
                    "input": json.loads(function.get("arguments") or "{}"),
                }
            )

        return {
            "stop_reason": "end_turn" if not tool_calls else "tool_use",
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

    # Rebuilds an OpenAI-compatible assistant message from normalized content
    # blocks (the inverse of parse_response).
    @staticmethod
    def _assistant_message(content: str | list[dict[str, Any]]) -> dict[str, Any]:
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content

        text_blocks = [b for b in blocks if b["type"] == "text"]
        tool_blocks = [b for b in blocks if b["type"] == "tool_use"]

        message: dict[str, Any] = {
            "role": "assistant",
            "content": "".join(b["text"] for b in text_blocks),
        }
        if tool_blocks:
            message["tool_calls"] = [
                {
                    "id": b["id"],
                    "type": "function",
                    "function": {"name": b["name"], "arguments": json.dumps(b["input"])},
                }
                for b in tool_blocks
            ]
        return message
