#!/usr/bin/env python3
"""Boukensha Step 1: The Struct Skeleton — runnable smoke test.

Port of ``examples/example.rb``. Mirrors its output so the two can be run
side by side against the same ``.boukensha/`` directory.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow running this script directly without installing the package first,
# mirroring the Ruby example's `require_relative "../lib/boukensha"`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boukensha.config import Config  # noqa: E402
from boukensha.context import Context  # noqa: E402
from boukensha.tasks.player import Player  # noqa: E402
from boukensha.tool import Tool  # noqa: E402


def main() -> None:
    os.environ.setdefault(
        "BOUKENSHA_DIR", str(Path(__file__).resolve().parents[3] / ".boukensha")
    )

    config = Config()
    player_settings = config.tasks("player")
    system_prompt = Player.system_prompt(
        player_settings,
        user_prompts_dir=config.user_prompts_dir,
    )

    ctx = Context(task=Player, system=system_prompt)

    ctx.register_tool(
        Tool(
            "move",
            "Move the player in a direction (north, south, east, west, up, down)",
            {"direction": {"type": "string", "description": "The direction to move"}},
            lambda direction: f"You move {direction} into a torch-lit corridor.",
        )
    )

    ctx.add_message("user", "Explore north and tell me what you find.")
    ctx.add_message("assistant", "Sure, let me head north and take a look.")

    print("=== Boukensha Step 1: Struct Skeleton ===")
    print()
    print(f"Config:   {config!r}")
    print(f"Context:  {ctx!r}")
    print(f"Tool:     {ctx.tools['move']!r}")
    print("Messages:")
    for message in ctx.messages:
        print(f"  {message!r}")


if __name__ == "__main__":
    main()
