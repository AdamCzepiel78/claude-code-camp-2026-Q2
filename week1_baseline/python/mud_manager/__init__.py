"""Port of ``week1_baseline/mud_manager_mcp`` (Ruby gem ``mud_manager``, vendored here
because no PyPI package provides CircleMUD session management).

Lives one level up from any single step (``python/mud_manager/``, a sibling of
``python/10_standard_tool_library/`` etc.) — mirroring the Ruby original, which
is its own gem (``week1_baseline/mud_manager_mcp``) pulled in as a dependency by
each step's gemspec rather than duplicated per step. Steps that need it add
this directory's parent to ``sys.path`` before importing (see
``boukensha/tools/mud.py``).

Provides :class:`~mud_manager.session.Session` (a long-lived telnet connection
with background buffering and IAC stripping) and :mod:`~mud_manager.primitives`
(a stateless library of typed CircleMUD command builders).
"""

from __future__ import annotations

from mud_manager import primitives
from mud_manager.session import (
    ConnectionError,
    LoginError,
    MudTimeoutError,
    Session,
    SessionError,
)

__all__ = [
    "Session",
    "SessionError",
    "ConnectionError",
    "LoginError",
    "MudTimeoutError",
    "primitives",
]
