"""Port of ``lib/boukensha/mcp_client.rb``.

A minimal Model Context Protocol client speaking JSON-RPC 2.0 over a
subprocess's stdin/stdout.

Hand-rolled rather than using the ``mcp`` PyPI package, for the same reason the
rest of BOUKENSHA avoids dependencies: the protocol is small enough to read, and
an MCP server is just a program you talk to over two pipes.

This is what makes the tool layer language-neutral. The MUD tools are defined
once, in the Ruby ``mud_manager`` MCP server; this client discovers them at
runtime. Nothing about the tools is restated here — which is the whole point,
since ``boukensha/tools/mud.py`` currently restates all 27 of them by hand.
"""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from typing import Any

from boukensha.version import VERSION

PROTOCOL_VERSION = "2025-06-18"


class McpError(Exception):
    pass


class McpProtocolError(McpError):
    pass


class McpClient:
    """Spawn an MCP server, shake hands, discover tools, call them.

    ``timeout`` is generous by default because ``session_open`` pays a ~6s MUD
    login before it answers.
    """

    def __init__(
        self,
        *,
        command: list[str],
        env: dict[str, str] | None = None,
        timeout: float = 60.0,
        debug: bool = False,
    ) -> None:
        self._command = command
        self._env = env or {}
        self._timeout = timeout
        self._debug = debug
        self._next_id = 0
        self._proc: subprocess.Popen[str] | None = None
        self._responses: queue.Queue[dict[str, Any]] = queue.Queue()
        self._lock = threading.Lock()
        self._tools: list[dict[str, Any]] | None = None
        self.server_info: dict[str, Any] = {}
        self.instructions: str | None = None

    def start(self) -> "McpClient":
        import os

        environment = {**os.environ, **self._env}
        self._proc = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            text=True,
            bufsize=1,  # line buffered
        )

        # Both pipes get their own draining thread. A server that logs faster
        # than we read would otherwise block forever on a full pipe buffer — a
        # classic subprocess deadlock that only appears under load.
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

        result = self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "boukensha", "version": VERSION},
            },
        )

        negotiated = result.get("protocolVersion")
        if negotiated != PROTOCOL_VERSION:
            print(
                f"[mcp] server speaks {negotiated}, we speak {PROTOCOL_VERSION} — continuing",
                file=sys.stderr,
            )

        self.server_info = result.get("serverInfo") or {}
        self.instructions = result.get("instructions")

        self._notify("notifications/initialized")
        return self

    @property
    def tools(self) -> list[dict[str, Any]]:
        """Tool descriptors straight from the server, cached for the process."""
        if self._tools is None:
            self._tools = self._request("tools/list").get("tools") or []
        return self._tools

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """Invoke a tool and return its text content.

        An MCP result carries ``isError`` to separate "the tool ran and reports a
        problem" from "the call itself failed". The former is folded into the
        returned string rather than raised: BOUKENSHA tools answer the agent with
        an ``error: …`` message so it can correct itself, exactly as the
        in-process MUD tools do.
        """
        result = self._request("tools/call", {"name": name, "arguments": arguments or {}})
        blocks = result.get("content") or []
        return "\n".join(b.get("text", "") for b in blocks if b.get("text") is not None)

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.stdin and not self._proc.stdin.closed:
                self._proc.stdin.close()  # documented MCP stdio shutdown signal
            self._proc.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            self._proc.kill()
        finally:
            self._proc = None

    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # ---------- internals ----------------------------------------------------

    def _read_stdout(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        for line in self._proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self._responses.put(json.loads(line))
            except json.JSONDecodeError:
                print(f"[mcp] malformed line: {line[:120]}", file=sys.stderr)

    def _read_stderr(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        for line in self._proc.stderr:
            if self._debug:
                print(f"[mcp] {line.rstrip()}", file=sys.stderr)

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            self._next_id += 1
            request_id = self._next_id
            message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
            if params is not None:
                message["params"] = params

            self._write(message)
            response = self._await_response(request_id)

            if "error" in response:
                err = response["error"]
                raise McpProtocolError(
                    f"{method} failed ({err.get('code')}): {err.get('message')}"
                )
            return response.get("result") or {}

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        with self._lock:
            message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
            if params is not None:
                message["params"] = params
            self._write(message)

    def _write(self, message: dict[str, Any]) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise McpError("MCP server is not running")
        try:
            self._proc.stdin.write(json.dumps(message) + "\n")
            self._proc.stdin.flush()
        except BrokenPipeError as e:
            raise McpError("MCP server exited") from e

    def _await_response(self, request_id: int) -> dict[str, Any]:
        """Wait for the response carrying our id, skipping any notification."""
        while True:
            try:
                message = self._responses.get(timeout=self._timeout)
            except queue.Empty as e:
                raise McpError(f"MCP server did not respond within {self._timeout}s") from e

            if message.get("id") == request_id:
                return message
