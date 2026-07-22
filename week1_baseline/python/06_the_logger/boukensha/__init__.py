"""Boukensha — Step 6: The Logger.

Port of ``lib/boukensha.rb``. Besides re-exporting the public classes, this
module holds process-wide state that the Ruby source keeps as ``Boukensha``
class methods: a memoized ``config()`` singleton and ``quiet`` / ``debug``
flags. ``debug()`` gates the logger's ``raw`` (full-response) lines.
"""

from __future__ import annotations

from boukensha.agent import Agent
from boukensha.client import Client
from boukensha.config import Config
from boukensha.context import Context
from boukensha.errors import ApiError, UnknownToolError, UnsupportedModelError
from boukensha.logger import Logger
from boukensha.message import Message
from boukensha.prompt_builder import PromptBuilder
from boukensha.registry import Registry
from boukensha.tasks.player import Player
from boukensha.tool import Tool

_config: Config | None = None
_quiet: bool = False
_debug: bool = False


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
    "UnknownToolError",
    "UnsupportedModelError",
    "ApiError",
    "config",
    "set_quiet",
    "quiet",
    "set_debug",
    "debug",
]
