"""Port of the ``mcp_server`` Ruby gem — a domain-free MCP server framework.

Supplies the JSON-RPC 2.0 stdio transport and the MCP lifecycle; you supply the
tools::

    from mcp_server import Server, ToolTable

    tools = ToolTable()

    @tools.add("greet", "Say hello.", {"name": {"type": "string"}}, required=["name"])
    def greet(args):
        return f"hello, {args['name']}"

    Server(tools=tools, name="greeter", version="1.0.0").run()

Two reference implementations exist deliberately — this one and the Ruby gem.
The transport has no concurrency, so porting it per language is cheap, and it
is what lets non-Ruby bootcampers write MCP servers of their own. (The telnet
*engine* in ``mud_manager_mcp`` is the opposite case and stays centralised.)
"""

from __future__ import annotations

from mcp_server.server import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    PROTOCOL_VERSION,
    RpcError,
    Server,
    ToolProvider,
)
from mcp_server.tool_table import ToolTable

__all__ = [
    "Server",
    "ToolTable",
    "ToolProvider",
    "RpcError",
    "PROTOCOL_VERSION",
    "PARSE_ERROR",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "INVALID_PARAMS",
    "INTERNAL_ERROR",
]
