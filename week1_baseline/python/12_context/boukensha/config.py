"""Configuration loading for the Boukensha agent.

Port of ``lib/boukensha/config.rb``. The per-task ``Tasks::Base``/``Tasks::Player``
indirection used by every prior step is gone as of this step — ``Config`` now
exposes ``provider_type``/``model``/``system_prompt`` and the agent's limit
settings directly, reading straight from ``settings.yaml``.
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
    """Loads and exposes settings from a ``.boukensha/`` directory."""

    def __init__(self) -> None:
        self.dir: Path = self._resolve_dir()
        self._load_env()
        self.settings: dict[str, Any] = self._load_settings()
        self.system_prompt: str | None = self._load_system_prompt()

    # ---------- provider -----------------------------------------------------

    @property
    def provider_type(self) -> str:
        return self.dig("tasks", "player", "provider") or "anthropic"

    @property
    def model(self) -> str:
        return self.dig("tasks", "player", "model") or "claude-haiku-4-5"

    # ---------- system prompt -------------------------------------------------

    def system_override(self) -> bool:
        # Declared to mirror the Ruby source exactly; not currently read by
        # anything else in this codebase (Ruby's own `system_override?` has no
        # call sites either) — kept for fidelity, not because it's wired up.
        return self.dig("system", "override") is True

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

    # ---------- MCP servers ------------------------------------------------

    @property
    def mcp_servers(self) -> dict[str, Any]:
        """Additional MCP servers declared in settings.yaml's ``mcp_servers:``.

        A mapping of name => spec (``command``/``env``/``after_connect``/``only``/
        ``except``); empty when none are declared. The MUD is wired separately —
        it carries an in-process fallback (``mud_mcp=False``) and a reachability
        probe that no generic server has. This block is for any *extra* server a
        user plugs in by configuration alone, with no new code.
        """
        return self.dig("mcp_servers") or {}

    # ---------- agent limits -------------------------------------------------
    # Static per-turn circuit breakers, read where the agent is constructed.
    # A value of 0 or None means "disabled" (no ceiling) — useful for debugging.

    @property
    def agent_max_iterations(self) -> int:
        v = self.dig("agent", "max_iterations")
        return 25 if v is None else int(v)

    @property
    def agent_max_output_tokens(self) -> int:
        v = self.dig("agent", "max_output_tokens")
        return 1024 if v is None else int(v)

    @property
    def agent_max_turn_tokens(self) -> int:
        v = self.dig("agent", "max_turn_tokens")
        return 60_000 if v is None else int(v)

    @property
    def agent_compaction_threshold(self) -> float:
        v = self.dig("agent", "compaction_threshold")
        return 0.85 if v is None else float(v)

    # ---------- low-level helpers -------------------------------------------

    def dig(self, *keys: str) -> Any:
        """Fetch a nested key path from settings, e.g. ``dig("provider", "model")``."""
        node: Any = self.settings
        for key in keys:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        return node

    def __repr__(self) -> str:
        return f"#<Boukensha.Config dir={self.dir} provider={self.provider_type} model={self.model}>"

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

    def _load_system_prompt(self) -> str | None:
        """Resolves the system prompt.

        When the player task opts into a prompt override
        (``tasks.player.prompt_override.system: true``), the task-scoped file
        ``prompts/player/system.md`` (inside the *config* directory) wins;
        otherwise — and as a fallback — the flat ``prompts/system.md`` (also
        inside the config directory) is used. Returns ``None`` when neither
        exists. Unlike every prior step, there is no step-bundled default to
        fall back to: a config directory with no ``prompts/system.md`` means
        the agent runs with no system prompt unless one is passed explicitly.
        """
        if self.dig("tasks", "player", "prompt_override", "system") is True:
            task_file = self.dir / "prompts" / "player" / "system.md"
            if task_file.exists():
                return task_file.read_text(encoding="utf-8").strip()

        system_file = self.dir / "prompts" / "system.md"
        if system_file.exists():
            return system_file.read_text(encoding="utf-8").strip()
        return None
