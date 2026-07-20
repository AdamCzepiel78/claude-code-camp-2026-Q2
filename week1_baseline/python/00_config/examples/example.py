#!/usr/bin/env python3
"""Boukensha Step 0: Configuration — runnable smoke test.

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

from boukensha.config import PROMPTS_DIR, Config  # noqa: E402
from boukensha.tasks.player import Player  # noqa: E402


def main() -> None:
    # Override the config directory so the example works from the repo root.
    # In real usage a user's ~/.boukensha is picked up automatically.
    os.environ.setdefault(
        "BOUKENSHA_DIR", str(Path(__file__).resolve().parents[3] / ".boukensha")
    )

    config = Config()
    player_settings = config.tasks("player")

    print("=== Boukensha Step 0: Configuration ===")
    print()
    print(f"Config dir:     {config.dir}")
    print(f"Tasks:          {', '.join(config.tasks())}")
    print()
    print("-- player task --")
    print(f"Provider:       {Player.provider(player_settings)}")
    print(f"Model:          {Player.model(player_settings)}")
    print(f"Prompt override?{Player.prompt_override(player_settings)}")

    system_prompt = Player.system_prompt(
        player_settings,
        user_prompts_dir=config.user_prompts_dir,
        default_prompts_dir=PROMPTS_DIR,
    )
    preview = (system_prompt or "")[:60]
    print(f"System prompt:  {preview}...")
    print()
    print(f"MUD host:       {config.mud_host}:{config.mud_port}")
    print(f"MUD user:       {config.mud_username}")
    print()
    print(f"API key set?    {os.environ.get('ANTHROPIC_API_KEY') is not None}")
    print()
    print(repr(config))


if __name__ == "__main__":
    main()
