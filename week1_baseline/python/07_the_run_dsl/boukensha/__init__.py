"""Boukensha — Step 7: The Run DSL.

Port of ``lib/boukensha.rb``. Besides re-exporting the public classes and holding
process-wide state (a memoized ``config()`` singleton and ``quiet`` / ``debug``
flags), this module provides the top-level :func:`run` entry point — Ruby's
``Boukensha.run`` — which wires every primitive together so a caller only
describes *what* to do, not *how* to plumb it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

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
from boukensha.run_dsl import RunDSL
from boukensha.tasks.player import Player
from boukensha.tool import Tool

_config: Config | None = None
_quiet: bool = False
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


def set_quiet(value: bool = True) -> None:
    global _quiet
    _quiet = value


def quiet() -> bool:
    return _quiet


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
    task settings in ``.boukensha/settings.yaml``.
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

    ctx = Context(task=task_class, system=system)
    registry = Registry(ctx)

    if setup is not None:
        setup(RunDSL(registry))

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


__all__ = [
    "Config",
    "Player",
    "Tool",
    "Message",
    "Context",
    "Registry",
    "PromptBuilder",
    "Client",
    "Agent",
    "Logger",
    "RunDSL",
    "UnknownToolError",
    "UnsupportedModelError",
    "ApiError",
    "LoopError",
    "config",
    "set_quiet",
    "quiet",
    "set_debug",
    "debug",
    "run",
]
