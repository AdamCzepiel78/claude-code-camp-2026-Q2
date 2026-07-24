"""Boukensha — Step 11: A Terminal UI.

Port of ``lib/boukensha.rb``. Besides re-exporting the public classes and holding
process-wide state (a memoized ``config()`` singleton and a ``debug`` flag), this
module provides two top-level entry points: :func:`run` (one-shot, Ruby's
``Boukensha.run``) and :func:`repl` (interactive multi-turn loop, Ruby's
``Boukensha.repl``).

``repl()`` gains a ``tui: bool = True`` keyword: by default it wraps the plain
REPL from step 10 in a full-screen terminal UI (:mod:`boukensha.tui`, built on
Textual). Pass ``tui=False`` for the plain terminal loop instead — the same one
step 10 shipped, unchanged.

This step gives the agent a standard library of tools out of the box instead of
requiring manual registration:

- ``working_dir``: roots all tool calls to this directory (default: ``Path.cwd()``).
  Registers ``boukensha.tools.FileSystem`` (pwd, list_directory, read_file,
  write_file, delete_file, search_files) and ``boukensha.tools.Shell``
  (run_command) automatically. Pass ``working_dir=False`` to opt out entirely.
- ``allowed_commands``: list of shell-executable names the agent may run via
  ``run_command`` (e.g. ``["python", "git"]``). ``None`` (default) permits
  everything. Pass ``[]`` to disable ``run_command`` entirely.
- ``shell_timeout``: seconds before a ``run_command`` call is killed (default 30).
- ``mud``: dict of MUD connection options — registers all MUD gameplay tools and
  keeps a single session alive across every tool call. When ``None`` (default),
  ``config().mud_*`` values are used if ``mud_host``/``mud_username`` are set in
  ``settings.yaml``. Pass ``mud=False`` to disable entirely.
- ``mud_mcp``: where the MUD tools come from. ``True`` (default) sources them
  from the ``mud_manager_mcp`` server over MCP — defined once there and
  discovered at runtime, so this is the same tool set every language gets.
  Pass a dict to add options (``command``, ``autoconnect``, ``only``,
  ``except_``, ``debug``). Pass ``False`` to use the in-process
  ``boukensha.tools.Mud`` instead, which needs no Ruby subprocess but
  restates every tool by hand.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from boukensha import tools as Tools
from boukensha.agent import Agent
from boukensha.backends import Anthropic, Gemini, Mammouth, Ollama, OllamaCloud, OpenAI
from boukensha.backends.base import Base
from boukensha.client import Client
from boukensha.config import PROMPTS_DIR, Config
from boukensha.context import Context
from boukensha.errors import ApiError, LoopError, UnknownToolError, UnsupportedModelError
from boukensha.logger import Logger
from boukensha.message import Message
from boukensha.prompt_builder import PromptBuilder
from boukensha.registry import Registry
from boukensha.repl import Repl
from boukensha.run_dsl import RunDSL
from boukensha.tasks.player import Player
from boukensha.tool import Tool
from boukensha.version import VERSION

_config: Config | None = None
_debug: bool = False

# Which env var holds the API key for each backend (Ollama needs none).
_API_KEY_ENV: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "mammouth": "MAMMOUTH_API_KEY",
    "ollama_cloud": "OLLAMA_API_KEY",
}


def config() -> Config:
    """Memoized process-wide :class:`Config` (Ruby's ``Boukensha.config``)."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_debug(value: bool = True) -> None:
    global _debug
    _debug = value


def debug() -> bool:
    return _debug


def run(
    *,
    task: str,
    system: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
    log: Path | str | None = None,
    max_output_tokens: int | None = None,
    setup: Callable[[RunDSL], None] | None = None,
    working_dir: str | Path | bool = True,
    allowed_commands: list[str] | None = None,
    shell_timeout: int = 30,
    mud: dict[str, Any] | bool | None = None,
    mud_mcp: dict[str, Any] | bool = True,
    mcp_servers: dict[str, Any] | bool | None = None,
) -> str:
    """The top-level entry point (Ruby's ``Boukensha.run``).

    Wires together every primitive so the caller only describes *what* to do.
    Tools are declared in the ``setup`` callback, which receives a
    :class:`~boukensha.run_dsl.RunDSL`::

        def setup(t):
            @t.tool("read_file", description="...", parameters={"path": {...}})
            def read_file(path: str) -> str:
                ...

        result = boukensha.run(task="...", setup=setup)

    Options mirror the Ruby source; unset values fall back to the ``player``
    task settings in ``.boukensha/settings.yaml``. See the module docstring for
    ``working_dir``/``allowed_commands``/``shell_timeout``/``mud``.
    """
    cfg = config()  # loads .env; populates os.environ
    task_class = Player
    task_settings = cfg.tasks(task_class.task_name())

    if system is None:
        system = task_class.system_prompt(
            task_settings,
            user_prompts_dir=cfg.user_prompts_dir,
            default_prompts_dir=PROMPTS_DIR,
        )
    if model is None:
        model = task_class.model(task_settings)
    if backend is None:
        backend = task_class.provider(task_settings)
    if api_key is None and backend in _API_KEY_ENV:
        api_key = os.environ.get(_API_KEY_ENV[backend])

    resolved_working_dir = _resolve_working_dir(working_dir)
    ctx = Context(task=task_class, system=system, working_dir=resolved_working_dir)
    registry = Registry(ctx)

    if setup is not None:
        setup(RunDSL(registry))

    if resolved_working_dir is not None:
        Tools.FileSystem.register(registry, working_dir=resolved_working_dir)
        Tools.Shell.register(
            registry, working_dir=resolved_working_dir, timeout=shell_timeout,
            allowed_commands=allowed_commands,
        )

    resolved_mud, mud_provenance = _register_mud_tools(registry, cfg, mud=mud, mud_mcp=mud_mcp)
    mcp_provenance = _register_declared_servers(registry, cfg, mcp_servers)

    be = _build_backend(backend, model=model, api_key=api_key, ollama_host=ollama_host)

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = (
        max_output_tokens
        if max_output_tokens is not None
        else task_class.max_output_tokens(task_settings)
    )
    logger = Logger(
        log=log,
        snapshot={
            "task": task_class.task_name(),
            "max_iterations": effective_max_iterations,
            "max_output_tokens": effective_max_output_tokens,
            "model": model,
            "provider": backend,
            **({"mud_tools": mud_provenance} if mud_provenance else {}),
            **({"mcp_servers": mcp_provenance} if mcp_provenance else {}),
        },
    )
    agent = Agent(
        context=ctx,
        registry=registry,
        builder=builder,
        client=client,
        logger=logger,
        task_settings=task_settings,
        max_iterations=effective_max_iterations,
        max_output_tokens=effective_max_output_tokens,
    )

    ctx.add_message("user", task)
    try:
        return agent.run()
    finally:
        logger.close()


def repl(
    *,
    system: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
    log: Path | str | None = None,
    max_output_tokens: int | None = None,
    setup: Callable[[RunDSL], None] | None = None,
    working_dir: str | Path | bool = True,
    allowed_commands: list[str] | None = None,
    shell_timeout: int = 30,
    mud: dict[str, Any] | bool | None = None,
    mud_mcp: dict[str, Any] | bool = True,
    mcp_servers: dict[str, Any] | bool | None = None,
    tui: bool = True,
) -> None:
    """Interactive REPL — see :func:`run` for full option documentation.

    ``tui``: ``True`` (default) wraps the REPL in a Textual-based terminal UI
    (:mod:`boukensha.tui`). Pass ``tui=False`` (or the ``--no-tui`` CLI flag)
    for the plain terminal loop instead.
    """
    cfg = config()  # loads .env; populates os.environ
    task_class = Player
    task_settings = cfg.tasks(task_class.task_name())

    if system is None:
        system = task_class.system_prompt(
            task_settings,
            user_prompts_dir=cfg.user_prompts_dir,
            default_prompts_dir=PROMPTS_DIR,
        )
    if model is None:
        model = task_class.model(task_settings)
    if backend is None:
        backend = task_class.provider(task_settings)
    if api_key is None and backend in _API_KEY_ENV:
        api_key = os.environ.get(_API_KEY_ENV[backend])

    resolved_working_dir = _resolve_working_dir(working_dir)
    ctx = Context(task=task_class, system=system, working_dir=resolved_working_dir)
    registry = Registry(ctx)

    if setup is not None:
        setup(RunDSL(registry))

    if resolved_working_dir is not None:
        Tools.FileSystem.register(registry, working_dir=resolved_working_dir)
        Tools.Shell.register(
            registry, working_dir=resolved_working_dir, timeout=shell_timeout,
            allowed_commands=allowed_commands,
        )

    resolved_mud, mud_provenance = _register_mud_tools(registry, cfg, mud=mud, mud_mcp=mud_mcp)
    mcp_provenance = _register_declared_servers(registry, cfg, mcp_servers)

    be = _build_backend(backend, model=model, api_key=api_key, ollama_host=ollama_host)

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = (
        max_output_tokens
        if max_output_tokens is not None
        else task_class.max_output_tokens(task_settings)
    )
    logger = Logger(
        log=log,
        snapshot={
            "task": task_class.task_name(),
            "max_iterations": effective_max_iterations,
            "max_output_tokens": effective_max_output_tokens,
            "model": model,
            "provider": backend,
            **({"mud_tools": mud_provenance} if mud_provenance else {}),
            **({"mcp_servers": mcp_provenance} if mcp_provenance else {}),
        },
    )

    the_repl = Repl(
        context=ctx,
        registry=registry,
        builder=builder,
        client=client,
        logger=logger,
        task_settings=task_settings,
        max_iterations=effective_max_iterations,
        max_output_tokens=effective_max_output_tokens,
        config_dir=cfg.dir,
        provider=backend,
        model=model,
        version=VERSION,
        api_key=api_key,
        mud=resolved_mud,
    )

    try:
        if tui:
            try:
                from boukensha.tui import BoukenshaApp
            except ImportError as e:
                raise ImportError(
                    "boukensha: tui=True requires the 'textual' package "
                    "(pip install textual), or pass tui=False / --no-tui for "
                    "the plain terminal REPL."
                ) from e
            BoukenshaApp(the_repl).run()
        else:
            the_repl.start()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        logger.close()


def _build_backend(
    backend: str, *, model: str, api_key: str | None, ollama_host: str
) -> Base:
    if backend == "anthropic":
        return Anthropic(api_key=api_key, model=model)
    if backend == "openai":
        return OpenAI(api_key=api_key, model=model)
    if backend == "gemini":
        return Gemini(api_key=api_key, model=model)
    if backend == "mammouth":
        return Mammouth(api_key=api_key, model=model)
    if backend == "ollama":
        return Ollama(host=ollama_host, model=model)
    if backend == "ollama_cloud":
        return OllamaCloud(api_key=api_key, model=model)
    raise ValueError(
        f"Unknown backend {backend!r}. "
        "Use 'anthropic', 'openai', 'gemini', 'mammouth', 'ollama', or 'ollama_cloud'."
    )


def _resolve_working_dir(working_dir: str | Path | bool) -> Path | None:
    """``True`` (default) → ``Path.cwd()`` at call time; ``False`` → disabled;
    a path → used as-is. A plain ``Path.cwd()`` default argument would be
    evaluated once at import time instead of per call, so the tri-state
    True/False/path form is used instead of a mutable default.
    """
    if working_dir is False:
        return None
    if working_dir is True:
        return Path.cwd()
    return Path(working_dir)


def _register_mud_tools(
    registry: Registry,
    cfg: Config,
    *,
    mud: dict[str, Any] | bool | None,
    mud_mcp: dict[str, Any] | bool,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Register the MUD gameplay tools, either in-process or via the MCP server.

    Both paths register tools under the same names (look, move, attack, …), so
    they are mutually exclusive — ``mud_mcp`` wins when both are requested.
    Returns ``(connection, provenance)``. The connection drives the REPL banner;
    the provenance is recorded in the session log so it is afterwards visible
    *which* implementation served the MUD tools. The tool names differ between
    the two paths, but relying on that to tell them apart is guesswork; this
    states it.
    """
    if mud is False:                      # explicit opt-out wins
        return None, None

    # A dict in ``mud`` is a connection override; otherwise fall back to config.
    # No connection settings anywhere means no MUD tools at all — which also
    # keeps us from spawning an MCP server for an agent that will never play.
    connection = mud if isinstance(mud, dict) else _mud_opts_from_config(cfg)
    if connection is None:
        return None, None

    if mud_mcp:
        overrides = mud_mcp if isinstance(mud_mcp, dict) else {}
        client = Tools.MudMcp.register(registry, **{**connection, **overrides})
        provenance = {
            "source": "mcp",
            "server": client.server_info.get("name"),
            "server_version": client.server_info.get("version"),
        }
        return connection, {k: v for k, v in provenance.items() if v is not None}

    Tools.Mud.register(registry, **connection)
    return connection, {"source": "in_process"}


def _register_declared_servers(
    registry: Registry,
    cfg: Config,
    mcp_servers: dict[str, Any] | bool | None,
) -> list[dict[str, Any]] | None:
    """Connect any MCP servers declared in settings.yaml's ``mcp_servers:``
    block (or passed explicitly as a dict), on top of the MUD.

    This is the config-driven path: a user plugs in a Kubernetes or filesystem
    server by editing YAML, with no new code. Tool-name collisions across
    servers are namespaced by :mod:`boukensha.mcp.servers`; the MUD's tools take
    part in that too.

    - ``mcp_servers=None`` → use settings.yaml's ``mcp_servers`` block (default)
    - ``mcp_servers={...}`` → use this dict instead
    - ``mcp_servers=False`` → connect none, even if declared in settings.yaml

    Returns the per-server provenance (recorded in the session log) or ``None``.
    """
    if mcp_servers is False:
        return None

    specs = mcp_servers if isinstance(mcp_servers, dict) else cfg.mcp_servers
    if not specs:
        return None

    _clients, provenance = Tools.Mcp.connect(registry, specs)
    return provenance


def _resolve_mud(mud: dict[str, Any] | bool | None, cfg: Config) -> dict[str, Any] | None:
    """``False`` → disabled; a dict → used as-is; ``None`` (default) → build
    from ``cfg`` (used when ``mud`` is not passed to ``run``/``repl``).
    """
    if mud is False:
        return None
    if mud is not None:
        return mud
    return _mud_opts_from_config(cfg)


def _mud_opts_from_config(cfg: Config) -> dict[str, Any] | None:
    """Build a mud options dict from config. Returns ``None`` if no MUD host
    is configured."""
    if not cfg.mud_host or not cfg.mud_username:
        return None
    return {
        "host": cfg.mud_host,
        "port": cfg.mud_port,
        "name": cfg.mud_username,
        "password": cfg.mud_password,
    }


__all__ = [
    "Config",
    "Player",
    "Tool",
    "Tools",
    "Message",
    "Context",
    "Registry",
    "PromptBuilder",
    "Client",
    "Agent",
    "Logger",
    "RunDSL",
    "Repl",
    "VERSION",
    "UnknownToolError",
    "UnsupportedModelError",
    "ApiError",
    "LoopError",
    "config",
    "set_debug",
    "debug",
    "run",
    "repl",
]
