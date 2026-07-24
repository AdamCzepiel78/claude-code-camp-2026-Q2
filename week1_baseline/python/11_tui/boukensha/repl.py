"""Port of ``lib/boukensha/repl.rb``.

``Repl`` is the interactive session loop. It wraps the same primitives as a
single :func:`boukensha.run`, but instead of running once it stays alive: read a
task from the user, run the agent, print the reply, loop back to the prompt.

The ``Context`` is shared across every turn so conversation history accumulates
naturally — the agent sees the full transcript each time it is called.

``Repl`` no longer hard-codes ``print``/``input``. Three methods let a
different front-end (:mod:`boukensha.tui`, or any other) drive it:

  ``on_output(callback)``    route all output through ``callback`` instead of stdout
  ``handle_command(input)``  process a slash command; returns "quit", "command", or None
  ``run_turn(input)``        run one agent turn and route the result through the callback

Built-in commands (not sent to the agent):
  /help    print the command list
  /clear   wipe conversation history (tools stay registered)
  /exit    leave the REPL
  /quit    alias for /exit
"""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any, Callable, Literal

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
        mud: dict[str, Any] | None = None,
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
        self._mud = mud
        self._turn = 0
        self._output_cb: Callable[[str], None] | None = None

    # ---------- reader properties (Tui needs these for the status line) ------

    @property
    def logger(self) -> Logger:
        return self._logger

    @property
    def context(self) -> Context:
        return self._context

    @property
    def model(self) -> str | None:
        return self._model

    @property
    def version(self) -> str | None:
        return self._version

    # ---------- front-end hooks -----------------------------------------------

    def on_output(self, callback: Callable[[str], None]) -> None:
        """Register a callback that receives every string the REPL would
        otherwise print to stdout. When set, ``print`` is suppressed entirely
        and all output is routed through the callback instead. Used by
        :mod:`boukensha.tui`.
        """
        self._output_cb = callback

    def handle_command(self, text: str) -> Literal["quit", "command"] | None:
        """Handle a slash command. Returns "quit", "command", or None (not a
        command). Output is routed through the registered ``on_output``
        callback if present.
        """
        if text in ("/exit", "/quit"):
            self._output("Goodbye.")
            return "quit"
        if text == "/help":
            self._output(HELP)
            return "command"
        if text == "/clear":
            self._context.clear_messages()
            self._turn = 0
            self._output("(conversation history cleared)")
            return "command"
        return None

    def run_turn(self, text: str) -> None:
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
            self._output("")
            self._output(result)
        except LoopError as e:
            self._output(f"\n[error] {e}")
        except ApiError as e:
            self._output(f"\n[error] API call failed: {e}")

    def start(self) -> None:
        self._output(self.banner())

        while True:
            if self._output_cb is None:
                print(PROMPT, end="", flush=True)

            try:
                line = input()
            except EOFError:  # Ctrl-D
                break

            text = line.strip()
            if not text:
                continue

            result = self.handle_command(text)
            if result == "quit":
                break
            if result == "command":
                continue

            self.run_turn(text)

    # ---------- internals ----------------------------------------------------

    def _output(self, text: str) -> None:
        if self._output_cb is not None:
            self._output_cb(str(text))
        else:
            print(text)

    def banner(self) -> str:
        key_status = "✗ API key not set" if not self._api_key or not self._api_key.strip() else "✓ API key set"
        provider_line = f"{self._provider or 'default'} ({self._model or 'default'})  {key_status}"
        config_exists = bool(self._config_dir) and Path(self._config_dir).is_dir()
        config_line = (
            str(self._config_dir)
            if config_exists
            else f"{self._config_dir or '(default)'}  ✗ directory not found"
        )
        ver = self._version or "?.?.?"
        pad = " " * (9 - len(ver))
        mud_stat = self._mud_status_string()

        return (
            "\n"
            "╔══════════════════════════════════════╗\n"
            f"║  BOUKENSHA MUD Assistant (v{ver}){pad}║\n"
            "╚══════════════════════════════════════╝\n"
            f"  config:    {config_line}\n"
            f"  provider:  {provider_line}\n"
            f"  mud:       {mud_stat}\n"
            "\n"
            "  /clear           reset conversation history\n"
            "  /exit or /quit    leave the REPL\n"
        )

    def _mud_status_string(self) -> str:
        """Build the mud status string shown in the banner.

        Only checks TCP reachability — the tool session auto-connects at
        startup (in ``Tools.Mud.register``), so probing login here would
        cause a double-login.
        """
        if not self._mud:
            return "(not configured)"

        host = self._mud.get("host") or "localhost"
        port = self._mud.get("port") or 4000
        name = self._mud.get("name")

        return f"{host}:{port}  {self._probe_mud(host, port, name)}"

    @staticmethod
    def _probe_mud(host: str, port: int, name: str | None) -> str:
        try:
            with socket.create_connection((host, port), timeout=3):
                pass
        except OSError:
            return "✗ not reachable"

        return "(Reachable)" if name and str(name).strip() else "(Reachable, no credentials)"
