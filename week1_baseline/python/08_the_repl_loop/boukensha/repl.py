"""Port of ``lib/boukensha/repl.rb``.

``Repl`` is the interactive session loop. It wraps the same primitives as a
single :func:`boukensha.run`, but instead of running once it stays alive: read a
task from the user, run the agent, print the reply, loop back to the prompt.

The ``Context`` is shared across every turn so conversation history accumulates
naturally — the agent sees the full transcript each time it is called.

Built-in commands (not sent to the agent):
  /help    print the command list
  /quiet   suppress detailed logging
  /loud    re-enable logging
  /clear   wipe conversation history (tools stay registered)
  /exit    leave the REPL
  /quit    alias for /exit
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import boukensha
from boukensha.agent import Agent
from boukensha.client import Client
from boukensha.context import Context
from boukensha.errors import ApiError, LoopError
from boukensha.logger import Logger
from boukensha.prompt_builder import PromptBuilder
from boukensha.registry import Registry

PROMPT = "boukensha> "

HELP = (
    "Commands:\n"
    "  /quiet   suppress logging output\n"
    "  /loud    re-enable logging output\n"
    "  /clear   wipe conversation history (tools stay)\n"
    "  /exit    leave the REPL\n"
    "  /help    show this message\n"
)


class Repl:
    def __init__(
        self,
        *,
        context: Context,
        registry: Registry,
        builder: PromptBuilder,
        client: Client,
        logger: Logger,
        config_dir: Path | str | None = None,
        provider: str | None = None,
        model: str | None = None,
        version: str | None = None,
        api_key: str | None = None,
        task_settings: dict[str, Any] | None = None,
        max_iterations: int | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        self._context = context
        self._registry = registry
        self._builder = builder
        self._client = client
        self._logger = logger
        self._task_settings = task_settings
        self._max_iterations = max_iterations
        self._max_output_tokens = max_output_tokens
        self._config_dir = config_dir
        self._provider = provider
        self._model = model
        self._version = version
        self._api_key = api_key
        self._turn = 0

    def start(self) -> None:
        print(self._banner())

        while True:
            print(PROMPT, end="", flush=True)
            try:
                line = input()
            except EOFError:  # Ctrl-D
                break

            text = line.strip()
            if not text:
                continue

            if text in ("/exit", "/quit"):
                print("Goodbye.")
                break
            if text == "/help":
                print(HELP)
                continue
            if text == "/quiet":
                boukensha.set_quiet(True)
                print("(logging suppressed — type /loud to re-enable)")
                continue
            if text == "/loud":
                boukensha.set_quiet(False)
                print("(logging enabled)")
                continue
            if text == "/clear":
                self._context.clear_messages()
                self._turn = 0
                print("(conversation history cleared)")
                continue

            self._run_turn(text)

    # ---------- internals ----------------------------------------------------

    def _banner(self) -> str:
        key_status = (
            "✗ API key not set"
            if (self._api_key is None or not self._api_key.strip())
            else "✓ API key set"
        )
        provider_line = f"{self._provider or 'default'} ({self._model or 'default'})  {key_status}"

        config_exists = self._config_dir is not None and Path(self._config_dir).is_dir()
        config_line = (
            str(self._config_dir)
            if config_exists
            else f"{self._config_dir or '(default)'}  ✗ directory not found"
        )
        ver = self._version or "?.?.?"
        pad = " " * (9 - len(ver))

        return (
            "\n"
            "╔══════════════════════════════════════╗\n"
            f"║  BOUKENSHA MUD Assistant (v{ver}){pad}║\n"
            "╚══════════════════════════════════════╝\n"
            f"  config:    {config_line}\n"
            f"  provider:  {provider_line}\n"
            "\n"
            "  /quiet or /loud   toggle logging\n"
            "  /clear           reset conversation history\n"
            "  /exit or /quit    leave the REPL\n"
        )

    def _run_turn(self, text: str) -> None:
        self._turn += 1
        self._logger.turn(n=self._turn)

        self._context.add_message("user", text)

        agent = Agent(
            context=self._context,
            registry=self._registry,
            builder=self._builder,
            client=self._client,
            logger=self._logger,
            task_settings=self._task_settings,
            max_iterations=self._max_iterations,
            max_output_tokens=self._max_output_tokens,
        )
        try:
            result = agent.run()
            # Print the final response outside the logger so it is always
            # visible, even when boukensha.set_quiet(True) is active.
            print()
            print(result)
        except LoopError as e:
            print(f"\n[error] {e}")
        except ApiError as e:
            print(f"\n[error] API call failed: {e}")
