"""Port of ``lib/boukensha/models.rb`` — with a real fix, not a bug-for-bug copy.

Ruby's ``Models::TABLE`` is a *second*, standalone model -> context_window
table, checked before a backend object exists (``boukensha.rb`` needs
``context_window`` to build ``Context``, and does so before constructing the
backend). It duplicates data every backend's own ``MODELS`` table already
has, and only lists three Claude models — any other model (Gemini, OpenAI,
Ollama, and here, Mammouth, since this Python port keeps that backend) falls
back to a conservative ``DEFAULT_CONTEXT_WINDOW`` instead of its real,
correct window.

That table is unfixable by just adding more entries: this port keeps
``Mammouth``, and Mammouth's own ``MODELS`` reuses model *names* that also
exist in ``Anthropic.MODELS`` — e.g. ``"claude-haiku-4-5"`` is 200,000 tokens
directly against Anthropic but 1,000,000 tokens through Mammouth's proxy. A
lookup keyed on model name alone cannot disambiguate those two entries.

The actual fix, used in ``boukensha/__init__.py``: construct the backend
*before* ``Context`` (nothing between them needs the backend built later —
checked directly against the current construction order) and read
``backend.context_window`` — already correct, per-backend, no duplication,
no ambiguity, since ``backends/base.py``'s ``Base.context_window`` already
reads each backend's own ``model_info`` table.

``Models.context_window`` below is kept only as a secondary, best-effort
lookup for callers that want an estimate *without* a live backend instance
(e.g. a banner shown before connecting). It requires a provider name to stay
disambiguated — unlike Ruby's single-argument version, which could not tell
Mammouth's "claude-haiku-4-5" from Anthropic's.
"""

from __future__ import annotations

from boukensha.backends import Anthropic, Gemini, Mammouth, Ollama, OllamaCloud, OpenAI
from boukensha.backends.base import Base

DEFAULT_CONTEXT_WINDOW = 32_000

BACKENDS: dict[str, type[Base]] = {
    "anthropic": Anthropic,
    "openai": OpenAI,
    "gemini": Gemini,
    "mammouth": Mammouth,
    "ollama": Ollama,
    "ollama_cloud": OllamaCloud,
}


def context_window(provider: str, model: str) -> int:
    """Best-effort context window for ``model`` under ``provider``, without
    needing a live backend instance. Falls back to ``DEFAULT_CONTEXT_WINDOW``
    for an unknown provider or an unknown model under a known provider.
    """
    backend_cls = BACKENDS.get(provider)
    if backend_cls is None:
        return DEFAULT_CONTEXT_WINDOW

    info = backend_cls.model_info_for(model)
    if info is None:
        return DEFAULT_CONTEXT_WINDOW

    return info.get("context_window", DEFAULT_CONTEXT_WINDOW)
