#!/usr/bin/env python3
"""Boukensha Step 4: The API Client — runnable smoke test.

Port of ``examples/example.rb``. Mirrors its output so the two can be run
side by side against the same ``.boukensha/`` directory. Unlike steps 0-3,
this sends a real HTTP request to whatever provider/model is configured in
``.boukensha/settings.yaml``.
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
from boukensha.client import Client  # noqa: E402
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

    @registry.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "The file path to read"}},
    )
    def read_file(path: str) -> str:
        return Path(path).read_text()

    @registry.tool(
        "list_directory",
        description="List files in a directory",
        parameters={"path": {"type": "string", "description": "The directory path to list"}},
    )
    def list_directory(path: str) -> str:
        return "\n".join(sorted(p.name for p in Path(path).iterdir() if not p.name.startswith(".")))

    ctx.add_message("user", "What files are in the current directory?")

    provider = Player.provider(player_settings)
    model = Player.model(player_settings)

    backend: Base
    if provider == "anthropic":
        backend = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], model=model)
    elif provider == "openai":
        backend = OpenAI(api_key=os.environ["OPENAI_API_KEY"], model=model)
    elif provider == "gemini":
        backend = Gemini(api_key=os.environ["GEMINI_API_KEY"], model=model)
    elif provider == "ollama":
        backend = Ollama(model=model)
    elif provider == "ollama_cloud":
        backend = OllamaCloud(api_key=os.environ["OLLAMA_API_KEY"], model=model)
    elif provider == "mammouth":
        backend = Mammouth(api_key=os.environ["MAMMOUTH_API_KEY"], model=model)
    else:
        raise ValueError(f"Unsupported provider for player task: {provider}")

    builder = PromptBuilder(ctx, backend)
    client = Client(builder)

    print("=== BOUKENSHA Step 4: API Client ===")
    print()
    print(f"Config: {config!r}")
    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print(f"Sending request to {builder.url()}...")
    print()

    response = client.call()
    print("Raw response:")
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
