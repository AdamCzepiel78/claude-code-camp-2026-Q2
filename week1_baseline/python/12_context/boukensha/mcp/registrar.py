"""Port of ``lib/boukensha/mcp/registrar.rb``.

Registers the tools of *any* MCP server with the agent.

Domain-free: point it at a command, and whatever that server advertises through
``tools/list`` becomes agent tools. :mod:`boukensha.tools.mud_mcp` is a preset
over this; a bootcamper plugs in an unrelated server with no new code::

    boukensha.mcp.registrar.register(
        registry,
        command=["kubernetes-mcp-server", "--read-only"],
        env={"KUBECONFIG": "/path/to/config"},
        except_=["pods_delete"],
    )

## Stateful servers

Some servers hold state that must be initialised before their other tools
work — a MUD login, a database connection, a browser session. MCP has no
capability flag for that; the channel it *does* provide is the ``instructions``
string in the initialize handshake. This module folds that into the system
prompt (``use_instructions``), so the server explains its own lifecycle and the
agent acts on it, instead of the client hard-coding which tool comes first.

``after_connect`` is only an optimisation over the same idea: calling the
bootstrap tool eagerly saves the agent a turn (and, for the MUD, a ~6s login
mid-conversation). It is a configured tool name, not knowledge baked into this
file.
"""

from __future__ import annotations

import atexit
import sys
from typing import Any, Callable

from boukensha.mcp.client import Client
from boukensha.registry import Registry

# Tool names may only contain [a-zA-Z0-9_-] — a dot is rejected by the provider
# APIs (verified against a live 400). So a namespaced tool reads ``server__tool``,
# the same convention MCP hosts use elsewhere.
NAMESPACE_SEPARATOR = "__"


def register(
    registry: Registry,
    *,
    command: list[str] | None = None,
    env: dict[str, str | None] | None = None,
    only: list[str] | None = None,
    except_: list[str] | None = None,
    after_connect: str | None = None,
    use_instructions: bool = True,
    prefix: str | None = None,
    prefix_only: list[str] | None = None,
    client: Client | None = None,
    debug: bool = False,
) -> Client:
    """Discover an MCP server's tools and register them all.

    ``env`` values of ``None`` remove that variable from the child environment.
    ``only``/``except_`` restrict which advertised tools are registered.

    ``prefix`` namespaces tools as ``<prefix>__<tool>``. ``prefix_only`` of
    ``None`` namespaces every tool; a list namespaces just those names —
    :mod:`boukensha.mcp.servers` passes the list form so only tools that actually
    collide across servers get renamed, and everything else keeps the name the
    server published.

    ``client``: :mod:`boukensha.mcp.servers` connects every server up front so it
    can compute collisions before registering, then hands the live client in
    here. On the single-server path we connect it ourselves.

    Returns the client so the caller can close it; an interpreter-exit hook is
    installed too so a server holding a connection is not left dangling.
    """
    own_client = client is None
    if client is None:
        client = Client(command=command or [], env=env or {}, debug=debug)
        client.start()

    for descriptor in _selected(client.tools, only=only, except_=except_):
        wanted = prefix is not None and (
            prefix_only is None or descriptor["name"] in prefix_only
        )
        _register_one(registry, client, descriptor, prefix=prefix if wanted else None)

    if use_instructions:
        registry.context.append_system(client.instructions)

    if after_connect:
        result = client.call_tool(after_connect, {})
        if debug or result.startswith("error:"):
            print(f"[boukensha] mcp {after_connect}: {result}", file=sys.stderr)

    atexit.register(client.close)
    return client


def namespaced(prefix: str | None, name: str) -> str:
    """The agent-facing name for ``name`` under ``prefix``.

    Public so a multi-server manager can pre-compute namespaced names.
    """
    return name if prefix is None else f"{prefix}{NAMESPACE_SEPARATOR}{name}"


# ---------- internals --------------------------------------------------------


def _selected(
    tools: list[dict[str, Any]], *, only: list[str] | None, except_: list[str] | None
) -> list[dict[str, Any]]:
    if only is not None:
        tools = [t for t in tools if t["name"] in only]
    if except_ is not None:
        tools = [t for t in tools if t["name"] not in except_]
    return tools


def _register_one(
    registry: Registry, client: Client, descriptor: dict[str, Any], *, prefix: str | None
) -> None:
    remote_name = descriptor["name"]
    local_name = namespaced(prefix, remote_name)
    properties = (descriptor.get("inputSchema") or {}).get("properties") or {}

    # The agent sees local_name; the server is always called by its own
    # remote_name — prefixing is a client-side disambiguation, not something the
    # server knows about.
    registry.tool(
        local_name,
        description=descriptor.get("description", ""),
        parameters=properties,
    )(_make_handler(client, remote_name))


def _make_handler(client: Client, remote_name: str) -> Callable[..., str]:
    """Build the tool body.

    A factory rather than a closure written inline, so ``remote_name`` is bound
    per tool — defining the function in the loop would leave every handler
    pointing at the last tool registered.
    """

    def handler(**kwargs: Any) -> str:
        return client.call_tool(remote_name, _prune(kwargs))

    return handler


def _prune(args: dict[str, Any]) -> dict[str, Any]:
    """Drop None and blank arguments before they reach the server.

    BOUKENSHA's backends mark every declared parameter as required (see
    ``backends/anthropic.py``'s ``to_tools``), while MCP schemas have genuinely
    optional fields. The model therefore fills optionals with "" to satisfy the
    schema. Pruning turns that back into "argument omitted" — which is why this
    belongs here rather than in any one server's adapter: no MCP server means
    every parameter to be mandatory.
    """
    pruned: dict[str, Any] = {}
    for key, value in args.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        pruned[key] = value
    return pruned
