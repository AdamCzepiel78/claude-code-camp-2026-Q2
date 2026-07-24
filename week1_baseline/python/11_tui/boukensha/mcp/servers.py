"""Port of ``lib/boukensha/mcp/servers.rb``.

Connect the agent to several MCP servers at once.

One :func:`boukensha.mcp.registrar.register` call wires up one server; nothing
coordinates N. A real agent wants more than one — a MUD *and* a Kubernetes
server *and* a filesystem server — which raises three problems this module owns:
name collisions between servers, collecting every server's instructions, and
closing them all on exit.

## Collision policy

Two servers may both publish ``search``. Colliding names are namespaced as
``<server>__<tool>``; names unique across all servers are left exactly as the
server published them. So connecting a second server never silently renames the
tools of the first unless there is a genuine clash.

The separator is ``__``, not ``.`` — tool names may only contain
``[a-zA-Z0-9_-]``, and a dot is rejected by the provider APIs with a 400.
"""

from __future__ import annotations

import sys
from collections import Counter
from typing import Any

from boukensha.mcp import registrar as Registrar
from boukensha.mcp.client import Client
from boukensha.registry import Registry


def connect(
    registry: Registry,
    specs: dict[str, dict[str, Any]] | None,
    *,
    debug: bool = False,
) -> tuple[list[Client], list[dict[str, Any]]]:
    """Connect and register every server in ``specs``.

    ``specs``: ``{"mud": {"command": [...], "env": {...}, "after_connect":
    "session_open"}, ...}``. The key names the server and becomes its namespace
    on collision.

    Returns ``(clients, provenance)`` — provenance is recorded in the session log
    so it is afterwards visible which servers served which tools.
    """
    if not specs:
        return [], []

    # Connect everything first: collisions can only be computed once every
    # server has told us what it offers.
    started: list[dict[str, Any]] = []
    for key, spec in specs.items():
        client = Client(
            command=spec.get("command") or [], env=spec.get("env") or {}, debug=debug
        )
        client.start()
        started.append({"key": str(key), "spec": spec, "client": client})

    colliding = _collisions(started)
    if colliding:
        print(
            f"[boukensha] mcp tool-name collisions namespaced: {', '.join(sorted(colliding))}",
            file=sys.stderr,
        )

    clients: list[Client] = []
    provenance: list[dict[str, Any]] = []

    for entry in started:
        spec, client, key = entry["spec"], entry["client"], entry["key"]

        Registrar.register(
            registry,
            command=spec.get("command"),
            env=spec.get("env") or {},
            only=spec.get("only"),
            except_=spec.get("except"),
            after_connect=spec.get("after_connect"),
            use_instructions=spec.get("use_instructions", True),
            prefix=key,
            prefix_only=colliding,
            debug=debug,
            client=client,  # already connected above
        )

        clients.append(client)
        record = {
            "name": key,
            "server": (client.server_info or {}).get("name"),
            "server_version": (client.server_info or {}).get("version"),
            "tools": len(client.tools),
        }
        provenance.append({k: v for k, v in record.items() if v is not None})

    return clients, provenance


# ---------- internals --------------------------------------------------------


def _collisions(started: list[dict[str, Any]]) -> list[str]:
    counts: Counter[str] = Counter()
    for entry in started:
        for tool in entry["client"].tools:
            counts[tool["name"]] += 1
    return [name for name, n in counts.items() if n > 1]
