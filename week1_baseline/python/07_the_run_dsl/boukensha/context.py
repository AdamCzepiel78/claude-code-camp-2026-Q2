"""Port of ``lib/boukensha/context.rb``.

Holds everything Boukensha needs to make an API call. Nothing lives outside
of this.
"""

from __future__ import annotations

from typing import Any

from boukensha.message import Message
from boukensha.tool import Tool


class Context:
    def __init__(self, *, task: Any, system: str | None = None) -> None:
        self.task = task
        self.system = system
        self.messages: list[Message] = []
        self.tools: dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def add_message(
        self,
        role: str,
        content: str | list[dict[str, Any]],
        *,
        tool_use_id: str | None = None,
    ) -> None:
        self.messages.append(Message(role, content, tool_use_id))

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    @property
    def turn_count(self) -> int:
        return len(self.messages)

    def __repr__(self) -> str:
        task_name = self.task.task_name() if self.task is not None else None
        return f"#<Context task={task_name} turns={self.turn_count} tools={self.tool_count}>"
