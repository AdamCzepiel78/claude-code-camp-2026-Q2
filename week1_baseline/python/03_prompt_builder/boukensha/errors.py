"""Port of ``lib/boukensha/errors.rb``."""

from __future__ import annotations


class UnknownToolError(Exception):
    """Raised when :meth:`boukensha.registry.Registry.dispatch` is given an unregistered tool name."""


class UnsupportedModelError(Exception):
    """Raised when a backend is constructed with a model outside its ``MODELS`` table."""
