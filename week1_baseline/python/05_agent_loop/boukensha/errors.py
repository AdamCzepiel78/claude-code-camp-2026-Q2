"""Port of ``lib/boukensha/errors.rb``."""

from __future__ import annotations


class UnknownToolError(Exception):
    """Raised when :meth:`boukensha.registry.Registry.dispatch` is given an unregistered tool name."""


class ApiError(Exception):
    """Raised by :meth:`boukensha.client.Client.call` when an API request ultimately fails."""


class UnsupportedModelError(Exception):
    """Raised when a backend is constructed with a model outside its ``MODELS`` table."""


class LoopError(Exception):
    """Raised when the agent loop cannot make progress."""
