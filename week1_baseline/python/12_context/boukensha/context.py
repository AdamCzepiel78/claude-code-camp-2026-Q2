"""Port of ``lib/boukensha/context.rb``.

Holds everything Boukensha needs to make an API call. Nothing lives outside
of this.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from boukensha.message import Message
from boukensha.tool import Tool


class Context:
    def __init__(
        self,
        *,
        system: str | None = None,
        context_window: int = 200_000,
        working_dir: str | Path | None = None,
        compaction_threshold: float = 0.85,
    ) -> None:
        self.system = system
        self.context_window = context_window
        self.compaction_threshold = compaction_threshold
        self.working_dir: Path | None = (
            Path(working_dir).expanduser().resolve() if working_dir else None
        )
        self.messages: list[Message] = []
        self.tools: dict[str, Tool] = {}
        self.current_tokens = 0
        self.turn_tokens = 0

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

    def add_message(
        self,
        role: str,
        content: str | list[dict[str, Any]],
        *,
        tool_use_id: str | None = None,
    ) -> None:
        self.messages.append(Message(role, content, tool_use_id))

    def update_tokens(self, n: int) -> None:
        """Update the known context size from the last API response's input_tokens."""
        self.current_tokens = int(n or 0)

    def reset_turn_tokens(self) -> None:
        """Reset the cumulative per-turn spend counter. Called at the top of a turn."""
        self.turn_tokens = 0

    def add_turn_tokens(self, input_tokens: int | None, output_tokens: int | None) -> None:
        """Add one API call's input+output tokens to the cumulative per-turn total.

        This is the spend budget — distinct from current_tokens (window pressure).
        """
        self.turn_tokens += int(input_tokens or 0) + int(output_tokens or 0)

    def usage_fraction(self) -> float:
        """Fraction of the context window currently in use (0.0-1.0)."""
        return self.current_tokens / self.context_window if self.context_window > 0 else 0.0

    def usage_pct(self) -> int:
        """Integer percentage (0-100)."""
        return round(self.usage_fraction() * 100)

    def needs_compaction(self, *, threshold: float | None = None) -> bool:
        """True when we should compact before the next API call. Defaults to
        the configured compaction_threshold (a fraction of context_window)."""
        return self.usage_fraction() >= (threshold if threshold is not None else self.compaction_threshold)

    def compact_messages(self, *, target_fraction: float = 0.60) -> int:
        """Drop the oldest 40% of messages to free space, keeping at least 2.

        Resets current_tokens to 0 (will be updated by the next API response).
        Returns the number of messages dropped.
        """
        drop_count = min(math.ceil(len(self.messages) * 0.40), len(self.messages) - 2)
        drop_count = max(drop_count, 0)
        self.messages = self.messages[drop_count:]
        self.current_tokens = 0
        return drop_count

    def clear_messages(self) -> None:
        """Drop all conversation history, keeping tools and system prompt intact.

        Used by the REPL's ``/clear`` command. Ruby names this ``clear_messages!``.
        """
        self.messages = []
        self.current_tokens = 0

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    @property
    def turn_count(self) -> int:
        return len(self.messages)

    def __repr__(self) -> str:
        return (
            f"#<Context turns={self.turn_count} tools={self.tool_count} "
            f"window={self.context_window} current={self.current_tokens}>"
        )
