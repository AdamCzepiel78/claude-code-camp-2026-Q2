"""Port of ``lib/boukensha/errors.rb``."""

from __future__ import annotations


class UnknownToolError(Exception):
    """Raised when :meth:`boukensha.registry.Registry.dispatch` is given an unregistered tool name."""
