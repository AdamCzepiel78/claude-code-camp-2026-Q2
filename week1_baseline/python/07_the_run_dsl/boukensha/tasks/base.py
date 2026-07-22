"""Abstract, stateless base for per-task settings resolution.

Port of ``lib/boukensha/tasks/base.rb``. All behaviour is expressed as
classmethods that accept a task's settings dict (as returned by
``Config.tasks(name)``) — no instances of ``Base`` or its subclasses are
ever created. Concrete subclasses define :meth:`task_name`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class Base:
    """Provider/model + prompt resolution shared by every task."""

    DEFAULT_MAX_ITERATIONS = 25
    DEFAULT_MAX_OUTPUT_TOKENS = 1024

    @classmethod
    def task_name(cls) -> str:
        raise NotImplementedError(f"{cls.__name__} must define task_name()")

    @classmethod
    def provider(cls, settings: dict[str, Any]) -> str:
        value = cls._fetch(settings, "provider")
        if value is None:
            raise ValueError(
                f"tasks.{cls.task_name()}.provider is required in settings.yaml"
            )
        return value

    @classmethod
    def model(cls, settings: dict[str, Any]) -> str:
        value = cls._fetch(settings, "model")
        if value is None:
            raise ValueError(
                f"tasks.{cls.task_name()}.model is required in settings.yaml"
            )
        return value

    @classmethod
    def prompt_override(cls, settings: dict[str, Any], prompt: str = "system") -> bool:
        node = cls._fetch(settings, "prompt_override")
        if not isinstance(node, dict):
            return False
        return node.get(prompt) is True

    @classmethod
    def prompt(
        cls,
        settings: dict[str, Any],
        name: str = "system",
        *,
        user_prompts_dir: Path | None = None,
        default_prompts_dir: Path | None = None,
    ) -> str | None:
        if cls.prompt_override(settings, name):
            text = cls._read_user_prompt(name, user_prompts_dir=user_prompts_dir)
            if text is not None:
                return text

        return cls._read_default_prompt(name, default_prompts_dir=default_prompts_dir)

    @classmethod
    def system_prompt(
        cls,
        settings: dict[str, Any],
        *,
        user_prompts_dir: Path | None = None,
        default_prompts_dir: Path | None = None,
    ) -> str | None:
        return cls.prompt(
            settings,
            "system",
            user_prompts_dir=user_prompts_dir,
            default_prompts_dir=default_prompts_dir,
        )

    @classmethod
    def max_iterations(cls, settings: dict[str, Any]) -> int:
        return cls._integer_setting(settings, "max_iterations", cls.DEFAULT_MAX_ITERATIONS)

    @classmethod
    def max_output_tokens(cls, settings: dict[str, Any]) -> int:
        return cls._integer_setting(settings, "max_output_tokens", cls.DEFAULT_MAX_OUTPUT_TOKENS)

    # ---------- internals ----------------------------------------------------

    @staticmethod
    def _fetch(settings: dict[str, Any], key: str) -> Any:
        if not isinstance(settings, dict):
            return None
        return settings.get(key)

    @classmethod
    def _integer_setting(cls, settings: dict[str, Any], key: str, default: int) -> int:
        value = cls._fetch(settings, key)
        if value is None:
            return default
        return int(value)

    @classmethod
    def _read_user_prompt(
        cls, prompt_name: str, *, user_prompts_dir: Path | None
    ) -> str | None:
        if user_prompts_dir is None:
            return None
        return cls._read_file(Path(user_prompts_dir) / cls.task_name() / f"{prompt_name}.md")

    @classmethod
    def _read_default_prompt(
        cls, prompt_name: str, *, default_prompts_dir: Path | None
    ) -> str | None:
        if default_prompts_dir is None:
            return None
        return cls._read_file(Path(default_prompts_dir) / f"{prompt_name}.md")

    @staticmethod
    def _read_file(path: Path) -> str | None:
        return path.read_text(encoding="utf-8").strip() if path.exists() else None
