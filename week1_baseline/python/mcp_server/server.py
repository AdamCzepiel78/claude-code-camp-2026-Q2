"""Port of ``mcp_server/lib/mcp_server/server.rb``.

A Model Context Protocol server speaking JSON-RPC 2.0 over stdio.

Nothing domain-specific lives here. Everything that makes a server *that*
server is injected: its identity, its instructions, its tools, and what to do
on shutdown.

Unlike ``mud_manager_mcp``'s telnet layer — which is concurrency-heavy and was
deliberately centralised in one language — this transport is ~150 lines of
"read a line, parse JSON, dispatch, write a line". No threads, no timing, no
protocol state beyond a boolean. That is why porting it per language is cheap,
and it is what lets a Python bootcamper write an MCP server without touching
Ruby.

STDOUT IS THE PROTOCOL. Nothing may write to it but this class — which is why
every diagnostic goes to stderr, and why a tool provider must not ``print()``.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, Protocol

PROTOCOL_VERSION = "2025-06-18"

# JSON-RPC 2.0 error codes.
PARSE_ERROR = -32_700
INVALID_REQUEST = -32_600
METHOD_NOT_FOUND = -32_601
INVALID_PARAMS = -32_602
INTERNAL_ERROR = -32_603


class ToolProvider(Protocol):
    """What ``Server`` needs from whatever supplies its tools.

    ``call`` should return ``(message, True)`` for problems the caller could fix
    — a bad argument, a missing precondition — so the agent reads the message
    and corrects itself. Raise ``KeyError`` only for a genuinely unknown tool
    name; that becomes a JSON-RPC error rather than a tool result.
    """

    def descriptors(self) -> list[dict[str, Any]]: ...

    def call(self, name: str, args: dict[str, Any]) -> tuple[str, bool]: ...


class RpcError(Exception):
    """Raised internally to produce a JSON-RPC error response."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


class Server:
    def __init__(
        self,
        *,
        tools: ToolProvider,
        name: str,
        version: str,
        instructions: str | None = None,
        on_shutdown: Callable[[], None] | None = None,
        input_stream: Any = None,
        output_stream: Any = None,
        debug: bool = False,
    ) -> None:
        self._tools = tools
        self._name = name
        self._version = version
        self._instructions = instructions
        self._on_shutdown = on_shutdown
        self._in = input_stream if input_stream is not None else sys.stdin
        self._out = output_stream if output_stream is not None else sys.stdout
        self._debug = debug

    def run(self) -> None:
        self._log(f"listening on stdio (protocol {PROTOCOL_VERSION})")
        try:
            for line in self._in:
                line = line.strip()
                if not line:
                    continue
                self._process(line)
            self._log("stdin closed, shutting down")
        finally:
            # The client closing stdin is MCP's documented shutdown signal for
            # stdio transports — this is where a server releases what it held.
            if self._on_shutdown is not None:
                self._on_shutdown()

    # ---------- internals ----------------------------------------------------

    def _process(self, line: str) -> None:
        try:
            message = json.loads(line)
        except json.JSONDecodeError as e:
            self._respond(None, error=(PARSE_ERROR, f"invalid JSON: {e}"))
            return

        if not isinstance(message, dict):
            self._respond(None, error=(INVALID_REQUEST, "request must be a JSON object"))
            return

        # A message without an "id" is a notification: handle it, answer
        # nothing. Replying to one is a protocol violation, not a harmless extra.
        if "id" not in message:
            self._log(f"notification: {message.get('method')}")
            return

        request_id = message["id"]
        try:
            self._respond(request_id, result=self._dispatch(message.get("method"), message.get("params") or {}))
        except RpcError as e:
            self._respond(request_id, error=(e.code, str(e)))
        except Exception as e:  # noqa: BLE001 - a server bug must not kill the loop
            self._log(f"unhandled: {type(e).__name__}: {e}")
            self._respond(request_id, error=(INTERNAL_ERROR, f"{type(e).__name__}: {e}"))

    def _dispatch(self, method: str | None, params: dict[str, Any]) -> dict[str, Any]:
        if method == "initialize":
            return self._handshake(params)
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": self._tools.descriptors()}
        if method == "tools/call":
            return self._call_tool(params)
        raise RpcError(METHOD_NOT_FOUND, f"unknown method: {method}")

    def _handshake(self, params: dict[str, Any]) -> dict[str, Any]:
        client = (params.get("clientInfo") or {}).get("name") or "unknown"
        self._log(f"client {client} requested {params.get('protocolVersion')}")

        payload: dict[str, Any] = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": self._name, "version": self._version},
        }

        # `instructions` is the protocol's channel for "here is how to drive me"
        # — which tool to call first, what state this server holds. A client can
        # fold it into the agent's prompt, so a stateful server explains its own
        # lifecycle instead of every client hard-coding it.
        if self._instructions:
            payload["instructions"] = self._instructions

        return payload

    def _call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        if name is None:
            raise RpcError(INVALID_PARAMS, "missing tool name")

        try:
            text, is_error = self._tools.call(name, params.get("arguments") or {})
        except KeyError as e:
            raise RpcError(INVALID_PARAMS, str(e).strip("'")) from e

        return {"content": [{"type": "text", "text": str(text)}], "isError": bool(is_error)}

    def _respond(
        self,
        request_id: Any,
        *,
        result: dict[str, Any] | None = None,
        error: tuple[int, str] | None = None,
    ) -> None:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
        if error is not None:
            code, message = error
            payload["error"] = {"code": code, "message": message}
        else:
            payload["result"] = result

        self._out.write(json.dumps(payload) + "\n")
        self._out.flush()

    def _log(self, message: str) -> None:
        if self._debug:
            print(f"[mcp_server:{self._name}] {message}", file=sys.stderr)
