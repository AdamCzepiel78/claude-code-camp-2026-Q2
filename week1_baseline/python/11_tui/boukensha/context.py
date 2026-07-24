"""Port of ``lib/boukensha/context.rb``.

Holds everything Boukensha needs to make an API call. Nothing lives outside
of this.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from boukensha.message import Message
from boukensha.tool import Tool


class Context:
    def __init__(
        self, *, task: Any, system: str | None = None, working_dir: str | Path | None = None
    ) -> None:
        self.task = task
        self.system = system
        self.messages: list[Message] = []
        self.tools: dict[str, Tool] = {}
        self.working_dir: Path | None = (
            Path(working_dir).expanduser().resolve() if working_dir else None
        )

    def append_system(self, text: str | None) -> None:
        """Append text to the system prompt after construction.

        Used by :mod:`boukensha.tools.mcp` to fold an MCP server's
        ``instructions`` into the prompt. The server declares how it wants to be
        driven — which tool to call first, what state it holds — and the agent
        reads that, instead of the client hard-coding knowledge of a particular
        server's tools.
        """
        if not text or not text.strip():
            return

        parts = [p for p in (self.system, text) if p and p.strip()]
        self.system = "\n\n".join(parts)

    def register_tool(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def clear_messages(self) -> None:
        """Drop all conversation history, keeping tools and system prompt intact.

        Used by the REPL's ``/clear`` command. Ruby names this ``clear_messages!``.
        """
        self.messages = []

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
