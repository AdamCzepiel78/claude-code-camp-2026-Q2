"""Port of ``lib/boukensha/tasks/player.rb`` — the main agentic-loop task."""

from __future__ import annotations

from boukensha.tasks.base import Base


class Player(Base):
    @classmethod
    def task_name(cls) -> str:
        return "player"
