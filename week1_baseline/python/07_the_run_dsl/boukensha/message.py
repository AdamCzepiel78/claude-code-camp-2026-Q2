"""Port of ``lib/boukensha/message.rb``.

A single unit of conversation between the user and the agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Message:
    role: str
    # Usually a plain string, but the agent loop stores an assistant turn as
    # the raw list of content blocks returned by the model (text and/or
    # tool_use blocks), so content is widened accordingly.
    content: str | list[dict[str, Any]]
    tool_use_id: str | None = None

    def __repr__(self) -> str:
        id_tag = f" [{self.tool_use_id}]" if self.tool_use_id else ""
        preview = self.content[:61] if isinstance(self.content, str) else str(self.content)[:61]
        return f"#<Message role={self.role}{id_tag} content={preview}...>"
