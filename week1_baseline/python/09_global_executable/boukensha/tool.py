"""Port of ``lib/boukensha/tool.rb``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    block: Callable[..., Any] | None = None

    def __repr__(self) -> str:
        return (
            f"#<Tool name={self.name} description={self.description[:41]} "
            f"params={list(self.parameters.keys())}>"
        )
