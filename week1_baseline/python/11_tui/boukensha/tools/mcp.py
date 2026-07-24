"""Port of ``lib/boukensha/tools/mcp.rb``.

Public entry point for MCP-sourced tools, sitting alongside
:mod:`boukensha.tools.file_system` and :mod:`boukensha.tools.shell` so all tool
registration reads the same way. The implementation lives in
:mod:`boukensha.mcp`.

    boukensha.tools.mcp.register(
        registry,
        command=["kubernetes-mcp-server", "--read-only"],
        except_=["pods_delete"],
    )

    boukensha.tools.mcp.connect(
        registry,
        {
            "mud":   {"command": [...], "after_connect": "session_open"},
            "notes": {"command": [...]},
        },
    )
"""

from __future__ import annotations

from typing import Any

from boukensha.mcp import registrar as _registrar
from boukensha.mcp import servers as _servers
from boukensha.mcp.client import Client
from boukensha.registry import Registry


def register(registry: Registry, **options: Any) -> Client:
    """One server. See :func:`boukensha.mcp.registrar.register` for the options."""
    return _registrar.register(registry, **options)


def connect(
    registry: Registry,
    specs: dict[str, dict[str, Any]] | None,
    *,
    debug: bool = False,
) -> tuple[list[Client], list[dict[str, Any]]]:
    """Several servers at once, namespacing any tool name they both publish.

    See :func:`boukensha.mcp.servers.connect`. Returns ``(clients, provenance)``.
    """
    return _servers.connect(registry, specs, debug=debug)
