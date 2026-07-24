"""Port of ``lib/boukensha/tools/mud_mcp.rb``.

MUD tools sourced from the ``mud_manager_mcp`` server. This is the default path
for MUD play; ``tools/mud.py`` remains as the in-process alternative.

Compare the two: ``tools/mud.py`` hard-codes 27 tools — every name, description
and parameter schema — and its Ruby twin states all of it again. This file
states none of them. It asks the server what it offers and registers whatever
comes back.

That is the entire argument for the MCP layer, and this file is the evidence:
it is a fraction of the size of ``tools/mud.py`` yet registers the identical
tool set, because the definitions now live in exactly one place. A tool added
to the server shows up here with no change to this file.

The telnet session, reader thread and IAC handling still have to exist — they
live inside ``mud_manager_mcp``. What goes away is the per-language duplication
of the tool descriptions on top of them. Note the trade: this path needs Ruby
on PATH to run the server, which is why the pure-Python ``tools/mud.py`` is
kept as a fallback.
"""

from __future__ import annotations

import atexit
import os
import shlex
import sys
from pathlib import Path
from typing import Any, Callable

from boukensha.mcp_client import McpClient
from boukensha.registry import Registry

# week1_baseline/mud_manager_mcp/bin/mud_manager_mcp, relative to this file:
# tools -> boukensha -> 10_standard_tool_library -> python -> week1_baseline
# Used in preference to the gem-installed executable so the step runs straight
# from a checkout, with no `gem install` step.
DEFAULT_SERVER = Path(__file__).resolve().parents[4] / "mud_manager_mcp" / "bin" / "mud_manager_mcp"


def register(
    registry: Registry,
    *,
    host: str | None = None,
    port: int | None = None,
    name: str | None = None,
    password: str | None = None,
    command: list[str] | None = None,
    autoconnect: bool = True,
    only: list[str] | None = None,
    except_: list[str] | None = None,
    debug: bool = False,
) -> McpClient:
    """Discover the MUD tools from the MCP server and register them.

    Returns the client so the caller can close it; an interpreter-exit hook is
    installed too so the MUD connection is not left dangling.
    """
    client = McpClient(
        command=command or _default_command(),
        env=_connection_env(host=host, port=port, name=name, password=password),
        debug=debug,
    )
    client.start()

    for descriptor in _selected(client.tools, only=only, except_=except_):
        _register_one(registry, client, descriptor)

    # Pay the ~6s MUD login now rather than inside the agent's first tool call.
    # Non-fatal: the agent can still call session_open and read the real error,
    # which is why this warns instead of raising.
    if autoconnect:
        result = client.call_tool("session_open", {})
        if debug or result.startswith("error:"):
            print(f"[boukensha] MUD session_open: {result}", file=sys.stderr)

    atexit.register(client.close)
    return client


# ---------- internals --------------------------------------------------------


def _default_command() -> list[str]:
    override = os.environ.get("BOUKENSHA_MUD_MCP_COMMAND")
    if override:
        return shlex.split(override)
    return ["ruby", str(DEFAULT_SERVER)]


def _connection_env(
    *, host: str | None, port: int | None, name: str | None, password: str | None
) -> dict[str, str]:
    pairs = {
        "MUD_HOST": host,
        "MUD_PORT": None if port is None else str(port),
        "MUD_NAME": name,
        "MUD_PASSWORD": password,
    }
    return {k: v for k, v in pairs.items() if v is not None}


def _selected(
    tools: list[dict[str, Any]], *, only: list[str] | None, except_: list[str] | None
) -> list[dict[str, Any]]:
    if only is not None:
        tools = [t for t in tools if t["name"] in only]
    if except_ is not None:
        tools = [t for t in tools if t["name"] not in except_]
    return tools


def _register_one(registry: Registry, client: McpClient, descriptor: dict[str, Any]) -> None:
    name = descriptor["name"]
    properties = (descriptor.get("inputSchema") or {}).get("properties") or {}

    registry.tool(
        name,
        description=descriptor.get("description", ""),
        parameters=properties,
    )(_make_handler(client, name))


def _make_handler(client: McpClient, name: str) -> Callable[..., str]:
    """Build the tool body.

    A factory rather than a closure written inline, so ``name`` is bound per
    tool — defining the function in the loop would leave every handler pointing
    at the last tool registered.
    """

    def handler(**kwargs: Any) -> str:
        return client.call_tool(name, _prune(kwargs))

    return handler


def _prune(args: dict[str, Any]) -> dict[str, Any]:
    """Drop None and blank arguments before they reach the server.

    BOUKENSHA's backends mark every declared parameter as required (see
    ``backends/anthropic.py``'s ``to_tools``), but MCP schemas have genuinely
    optional fields — ``session_id`` everywhere, and ``look`` takes none at all.
    The model therefore tends to fill optionals with "" to satisfy the schema.
    Pruning turns that back into "argument omitted", so ``look`` with a blank
    target describes the room instead of hunting for an object named "".
    """
    pruned: dict[str, Any] = {}
    for key, value in args.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        pruned[key] = value
    return pruned
