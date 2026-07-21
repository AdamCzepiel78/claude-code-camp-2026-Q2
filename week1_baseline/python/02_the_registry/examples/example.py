#!/usr/bin/env python3
"""Boukensha Step 2: The Tool Registry — runnable smoke test.

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
from boukensha.errors import UnknownToolError  # noqa: E402
from boukensha.registry import Registry  # noqa: E402
from boukensha.tasks.player import Player  # noqa: E402


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
    registry = Registry(ctx)

    # Notice that we now register the tools through the registry instead of
    # directly on the context, like in the previous step. They will still be
    # attached to context, which is why we pass it into our registry when we
    # initialize it.
    @registry.tool(
        "move",
        description="Move the player in a direction (north, south, east, west, up, down)",
        parameters={"direction": {"type": "string"}},
    )
    def move(direction: str) -> str:
        return f"You move {direction} into a torch-lit corridor."

    @registry.tool(
        "shout",
        description="Shout a message so everyone in the zone can hear it",
        parameters={"message": {"type": "string"}},
    )
    def shout(message: str) -> str:
        return message.upper()

    print("=== BOUKENSHA Step 2: Tool Registry ===")
    print()
    print(f"Config:  {config!r}")
    print(f"Context: {ctx!r}")
    print("Tools:")
    for t in ctx.tools.values():
        print(f"  {t!r}")
    print()

    # Here we are mimicking what the agent would do when it needs to call a
    # tool from the registry. We are still missing the actual code that
    # would decide when to call the registry for a tool.
    print("Dispatching 'shout' with message='dragon spotted'...")
    result = registry.dispatch("shout", {"message": "dragon spotted"})
    print(f"Result: {result}")
    print()

    print("Dispatching 'move' with direction='north'...")
    result = registry.dispatch("move", {"direction": "north"})
    print(f"Result: {result}")
    print()

    try:
        registry.dispatch("flee")
    except UnknownToolError as e:
        print(f"UnknownToolError caught: {e}")


if __name__ == "__main__":
    main()
