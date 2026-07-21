#!/usr/bin/env python3
"""Boukensha Step 3: The Prompt Builder — runnable smoke test.

Port of ``examples/example.rb``. Mirrors its output so the two can be run
side by side against the same ``.boukensha/`` directory.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Allow running this script directly without installing the package first,
# mirroring the Ruby example's `require_relative "../lib/boukensha"`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boukensha.backends import Anthropic, Gemini, Mammouth, Ollama, OllamaCloud, OpenAI  # noqa: E402
from boukensha.backends.base import Base  # noqa: E402
from boukensha.config import PROMPTS_DIR, Config  # noqa: E402
from boukensha.context import Context  # noqa: E402
from boukensha.prompt_builder import PromptBuilder  # noqa: E402
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
        default_prompts_dir=PROMPTS_DIR,
    )

    ctx = Context(task=Player, system=system_prompt)
    registry = Registry(ctx)

    @registry.tool("look", description="Look around the current room for details", parameters={})
    def look() -> str:
        return "A damp stone corridor stretches north. Torches flicker on the walls."

    @registry.tool(
        "move",
        description="Move the player in a direction (north, south, east, west, up, down)",
        parameters={"direction": {"type": "string", "description": "The direction to move"}},
    )
    def move(direction: str) -> str:
        return f"You move {direction} into a torch-lit corridor."

    ctx.add_message("user", "I just arrived in the dungeon. What's around me, and can you move north?")
    ctx.add_message("assistant", "Let me take a look around first.")
    ctx.add_message(
        "tool_result",
        "A damp stone corridor stretches north. Torches flicker on the walls.",
        tool_use_id="toolu_01X",
    )

    print("=== BOUKENSHA Step 3: Prompt Builder ===")
    provider = Player.provider(player_settings)
    model = Player.model(player_settings)

    backend: Base
    if provider == "anthropic":
        backend = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], model=model)
    elif provider == "ollama":
        backend = Ollama(model=model)
    elif provider == "ollama_cloud":
        backend = OllamaCloud(api_key=os.environ["OLLAMA_API_KEY"], model=model)
    elif provider == "openai":
        backend = OpenAI(api_key=os.environ["OPENAI_API_KEY"], model=model)
    elif provider == "gemini":
        backend = Gemini(api_key=os.environ["GEMINI_API_KEY"], model=model)
    elif provider == "mammouth":
        backend = Mammouth(api_key=os.environ["MAMMOUTH_API_KEY"], model=model)
    else:
        raise ValueError(f"Unsupported provider for player task: {provider}")

    builder = PromptBuilder(ctx, backend)

    print()
    print(f"Config: {config!r}")
    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print(json.dumps(builder.to_api_payload(), indent=2))


if __name__ == "__main__":
    main()
