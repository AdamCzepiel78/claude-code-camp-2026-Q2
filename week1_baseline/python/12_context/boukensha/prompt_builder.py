"""Port of ``lib/boukensha/prompt_builder.rb``.

Delegates ``Context`` serialization to whichever backend is passed in.
``PromptBuilder`` never calls an API itself — it only assembles the
payload/headers/url a caller would POST.
"""

from __future__ import annotations

from typing import Any

from boukensha.backends.base import Base
from boukensha.context import Context


class PromptBuilder:
    def __init__(self, context: Context, backend: Base) -> None:
        self._context = context
        self._backend = backend

    @property
    def backend(self) -> Base:
        return self._backend

    def to_messages(self) -> list[dict[str, Any]]:
        # Faithful port of the Ruby source: this calls the backend's
        # `to_messages` with only `messages`, matching `Anthropic`/`Gemini`'s
        # one-argument signature. `Ollama`/`OllamaCloud` define
        # `to_messages(system, messages)` (two arguments) instead, so calling
        # this method against one of those two backends raises a `TypeError`
        # here — same as Ruby's `ArgumentError` on the identical call.
        # `OpenAI` (as of this step) has no `to_messages` at all — it builds
        # Responses-API `input` items via `to_input`, so calling this method
        # against it raises `AttributeError` instead (Ruby: `NoMethodError`).
        # `to_api_payload` below is unaffected: each backend's own
        # `to_payload` calls its own message-building method internally, with
        # the right name and arity.
        return self._backend.to_messages(self._context.messages)

    def to_tools(self) -> list[dict[str, Any]]:
        return self._backend.to_tools(self._context.tools)

    def to_api_payload(
        self, *, max_output_tokens: int = 1024, tools: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        return self._backend.to_payload(
            self._context, max_output_tokens=max_output_tokens, tools=tools
        )

    def parse_response(self, response: dict[str, Any]) -> dict[str, Any]:
        # Delegates to the backend, which normalizes a provider response into
        # the common shape documented in backends.base:
        #   {"stop_reason": "tool_use" | "end_turn",
        #    "content": [{"type": "reasoning", ...} | {"type": "text", ...} | {"type": "tool_use", ...}]}
        return self._backend.parse_response(response)

    def headers(self) -> dict[str, str]:
        return self._backend.headers()

    def url(self) -> str:
        return self._backend.url()
