"""Port of ``lib/boukensha/backends/base.rb``.

Shared contract for every LLM backend: model validation against a static
``MODELS`` table, and cost/context-window lookups derived from it.
"""

from __future__ import annotations

from typing import Any, ClassVar

from boukensha.errors import UnsupportedModelError


class Base:
    """Model validation and cost/context-window accessors shared by every backend.

    Ruby's source overloads ``model_info`` as both a class method (``self.model_info(model)``,
    a table lookup) and an instance method (``model_info``, the memoized entry for this
    instance) — legal in Ruby's separate class/instance method namespaces but not in Python.
    Here the instance-facing name stays ``model_info`` (read by every cost/window accessor
    below); the classmethod lookup is renamed ``model_info_for``.
    """

    MODELS: ClassVar[dict[str, dict[str, Any]] | None] = None

    @classmethod
    def models(cls) -> dict[str, dict[str, Any]]:
        if cls.MODELS is None:
            raise NotImplementedError(f"{cls.__name__} must define MODELS")
        return cls.MODELS

    @classmethod
    def model_info_for(cls, model: str) -> dict[str, Any] | None:
        return cls.models().get(model)

    @classmethod
    def validate_model(cls, model: str) -> str:
        if cls.model_info_for(model) is not None:
            return model

        supported = ", ".join(sorted(cls.models()))
        raise UnsupportedModelError(
            f"{cls.__name__} does not support model {model!r}. Supported models: {supported}"
        )

    def __init__(self) -> None:
        self.model: str = ""
        self.model_info: dict[str, Any] = {}

    @property
    def context_window(self) -> int:
        return self.model_info["context_window"]

    @property
    def input_token_cost_per_million(self) -> float | None:
        return self.model_info["cost_per_million"]["input"]

    @property
    def output_token_cost_per_million(self) -> float | None:
        return self.model_info["cost_per_million"]["output"]

    @property
    def usage_unit(self) -> str:
        return self.model_info["usage_unit"]

    @property
    def usage_level(self) -> str | None:
        return self.model_info.get("usage_level")

    def estimate_cost(self, *, input_tokens: int, output_tokens: int) -> float | None:
        input_cost = self.input_token_cost_per_million
        output_cost = self.output_token_cost_per_million
        if input_cost is None or output_cost is None:
            return None

        return ((input_tokens * input_cost) + (output_tokens * output_cost)) / 1_000_000.0

    def _configure_model(self, model: str) -> None:
        self.model = self.__class__.validate_model(model)
        self.model_info = self.__class__.model_info_for(self.model) or {}
