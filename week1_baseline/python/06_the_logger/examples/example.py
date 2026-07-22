#!/usr/bin/env python3
"""Boukensha Step 6: The Logger — runnable smoke test.

Port of ``examples/example.rb``. Mirrors its output so the two can be run side
by side against the same ``.boukensha/`` directory. Sends real HTTP requests to
whatever provider/model is configured in ``.boukensha/settings.yaml`` and drives
the full agent loop (model → tool calls → tool results → …) until the model
stops asking for tools or the iteration limit is reached.

Unlike step 5, the per-iteration/tool trace is written as structured JSONL to
``.boukensha/sessions/<session-id>.jsonl`` rather than to the terminal; only the
header and the final response are printed. Call ``boukensha.set_debug(True)`` to
include the full raw API response in those log lines.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow running this script directly without installing the package first,
# mirroring the Ruby example's `require_relative "../lib/boukensha"`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boukensha.agent import Agent  # noqa: E402
from boukensha.backends import Anthropic, Gemini, Mammouth, Ollama, OllamaCloud, OpenAI  # noqa: E402
from boukensha.backends.base import Base  # noqa: E402
from boukensha.client import Client  # noqa: E402
from boukensha.config import PROMPTS_DIR, Config  # noqa: E402
from boukensha.context import Context  # noqa: E402
from boukensha.logger import Logger  # noqa: E402
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
    base_dir = Path(__file__).resolve().parent.parent

    ctx = Context(task=Player, system=system_prompt)
    registry = Registry(ctx)

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
    # Writes structured JSONL events to .boukensha/sessions/<session-id>.jsonl.
    # Call boukensha.set_debug(True) to include the full raw API response.
    logger = Logger()
    agent = Agent(
        context=ctx,
        registry=registry,
        builder=builder,
        client=client,
        logger=logger,
        task_settings=player_settings,
    )

    @registry.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "The file path to read"}},
    )
    def read_file(path: str) -> str:
        return (base_dir / path).read_text()

    @registry.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={"path": {"type": "string", "description": "The directory path to list"}},
    )
    def list_directory(path: str) -> str:
        return ", ".join(
            sorted(p.name for p in (base_dir / path).iterdir() if not p.name.startswith("."))
        )

    ctx.add_message(
        "user",
        "Read the README.md file and summarise what this MUD player assistant framework can do.",
    )

    print("=== BOUKENSHA Step 6: The Logger ===")
    print()
    print(f"Config: {config!r}")
    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print(f"Max iterations: {Player.max_iterations(player_settings)}")
    print(f"Max output tokens: {Player.max_output_tokens(player_settings)}")
    print()

    result = agent.run()

    print()
    print("=== FINAL RESPONSE ===")
    print(result)


if __name__ == "__main__":
    main()
