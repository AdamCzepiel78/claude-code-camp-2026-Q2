"""Configuration loading for the Boukensha agent.

Port of ``lib/boukensha/config.rb`` from the Ruby ``01_struct_skeleton`` step.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# The .boukensha config directory is resolved in this order:
#   1. BOUKENSHA_DIR environment variable
#   2. ~/.boukensha  (default)
DEFAULT_DIR: Path = Path.home() / ".boukensha"


class Config:
    """Loads and exposes settings from a ``.boukensha/`` directory.

    Configuration is organised by *task* — a role in the agentic loop bound
    to its own LLM (see :mod:`boukensha.tasks.base`). ``Config`` itself only
    knows how to locate the config directory and load ``.env`` /
    ``settings.yaml`` — it hands each task's settings dict to
    ``boukensha.tasks.base.Base`` subclasses for interpretation.
    """

    def __init__(self) -> None:
        self.dir: Path = self._resolve_dir()
        self._load_env()
        self.settings: dict[str, Any] = self._load_settings()

    # ---------- tasks -----------------------------------------------------

    def tasks(self, name: str | None = None) -> dict[str, Any]:
        """With no argument, the full ``tasks:`` mapping from settings.yaml.

        With a name, that task's settings dict, e.g. ``tasks("player")``.
        """
        all_tasks: dict[str, Any] = self.dig("tasks") or {}
        return all_tasks if name is None else all_tasks.get(name)

    @property
    def user_prompts_dir(self) -> Path:
        """The user's prompts directory, for per-task prompt overrides."""
        return self.dir / "prompts"

    # ---------- MUD connection ---------------------------------------------

    @property
    def mud_host(self) -> str:
        return self.dig("mud", "host") or "localhost"

    @property
    def mud_port(self) -> int:
        return self.dig("mud", "port") or 4000

    @property
    def mud_username(self) -> str | None:
        return self.dig("mud", "username")

    @property
    def mud_password(self) -> str | None:
        return self.dig("mud", "password")

    # ---------- low-level helpers -------------------------------------------

    def dig(self, *keys: str) -> Any:
        """Fetch a nested key path from settings, e.g. ``dig("mud", "host")``."""
        node: Any = self.settings
        for key in keys:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        return node

    def __repr__(self) -> str:
        return f"#<Boukensha.Config dir={self.dir} tasks={','.join(self.tasks())}>"

    # ---------- internals ----------------------------------------------------

    @staticmethod
    def _resolve_dir() -> Path:
        raw = os.environ.get("BOUKENSHA_DIR") or str(DEFAULT_DIR)
        return Path(raw).expanduser().resolve()

    def _load_env(self) -> None:
        env_file = self.dir / ".env"
        if env_file.exists():
            load_dotenv(env_file)

    def _load_settings(self) -> dict[str, Any]:
        settings_file = self.dir / "settings.yaml"
        if not settings_file.exists():
            return {}
        with settings_file.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
