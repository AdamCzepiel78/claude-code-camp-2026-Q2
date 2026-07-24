"""Standard tool library: FileSystem, Shell, Mud.

Each submodule exposes a ``register(registry, ...)`` function that registers
its tools on a :class:`~boukensha.registry.Registry`. See
``boukensha.run``/``boukensha.repl`` for the ``working_dir``/``allowed_commands``/
``shell_timeout``/``mud`` keyword args that drive auto-registration.
"""

from __future__ import annotations

from boukensha.tools import file_system as FileSystem
from boukensha.tools import mud as Mud
from boukensha.tools import mud_mcp as MudMcp
from boukensha.tools import shell as Shell

__all__ = ["FileSystem", "Shell", "Mud", "MudMcp"]
