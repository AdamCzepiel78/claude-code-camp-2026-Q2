"""Port of ``lib/boukensha/backends/ollama.rb``."""

from __future__ import annotations

from typing import Any, ClassVar

from boukensha.backends.base import Base
from boukensha.message import Message
from boukensha.tool import Tool


class Ollama(Base):
    MODELS: ClassVar[dict[str, dict[str, Any]]] = {
        "gemma3:12b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gpt-oss:20b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:e2b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:e4b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:12b": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:26b": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:31b": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "qwen3:30b": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "qwen3:8b": {
            "context_window": 40_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "deepseek-r1:8b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
    }

    def __init__(self, *, host: str = "http://localhost:11434", model: str) -> None:
        super().__init__()
        self._host = host
        self._configure_model(model)

    def to_messages(self, system: str | None, messages: list[Message]) -> list[dict[str, Any]]:
        system_message = [{"role": "system", "content": system}]
        conversation = []
        for msg in messages:
            if msg.role == "tool_result":
                conversation.append(
                    {"role": "tool", "tool_name": msg.tool_use_id, "content": msg.content}
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
            "stream": False,
            "messages": self.to_messages(context.system, context.messages),
            "tools": self.to_tools(context.tools) if tools is None else tools,
        }

    # Normalizes an Ollama /api/chat response into the common shape:
    #   {stop_reason: "tool_use" | "end_turn", content: [ {"type": "text", "text": ...} |
    #    {"type": "tool_use", "id": ..., "name": ..., "input": ...} ]}
    #
    # Ollama doesn't assign call ids, so the function name is reused as the id
    # (Ollama also matches tool results back to a call by name).
    def parse_response(self, response: dict[str, Any]) -> dict[str, Any]:
        message = response.get("message") or {}
        tool_calls = message.get("tool_calls") or []

        content: list[dict[str, Any]] = []
        if message.get("content"):
            content.append({"type": "text", "text": message["content"]})

        for tc in tool_calls:
            function = tc.get("function") or {}
            content.append(
                {
                    "type": "tool_use",
                    "id": function.get("name"),
                    "name": function.get("name"),
                    "input": function.get("arguments") or {},
                }
            )

        return {
            "stop_reason": "end_turn" if not tool_calls else "tool_use",
            "content": content,
        }

    def headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    def url(self) -> str:
        return f"{self._host}/api/chat"

    # ---------- internals ----------------------------------------------------

    # Rebuilds an Ollama assistant message from normalized content blocks
    # (the inverse of parse_response).
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
                {"function": {"name": b["name"], "arguments": b["input"]}} for b in tool_blocks
            ]
        return message
