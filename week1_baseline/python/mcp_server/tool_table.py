"""Port of ``mcp_server/lib/mcp_server/tool_table.py``.

A small builder for the tool-provider contract :class:`~mcp_server.server.Server`
expects. Using it is optional — any object with ``descriptors()`` and
``call(name, args)`` works — but it removes the boilerplate of hand-assembling
JSON Schema and dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class _Tool:
    name: str
    description: str
    schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]


class ToolTable:
    """Collect tools, then hand the table to a ``Server``.

    ``rescuable`` names the exceptions a *caller* could plausibly fix — a bad
    enum value, a missing precondition. Those come back as ``isError`` tool
    results carrying the message, so the agent reads it and corrects itself.
    Anything else propagates and becomes a JSON-RPC internal error, because a
    bug in the server is not something the agent can work around.
    """

    def __init__(self, *, rescuable: tuple[type[Exception], ...] = (ValueError,)) -> None:
        self._tools: dict[str, _Tool] = {}
        self._rescuable = rescuable

    def add(
        self,
        name: str,
        description: str,
        properties: dict[str, Any] | None = None,
        *,
        required: list[str] | None = None,
    ) -> Callable[[Callable[[dict[str, Any]], Any]], Callable[[dict[str, Any]], Any]]:
        """Register a tool. Used as a decorator so the metadata reads first::

            @tools.add("greet", "Say hello.", {"name": {"type": "string"}}, required=["name"])
            def greet(args):
                return f"hello, {args['name']}"
        """

        def register(handler: Callable[[dict[str, Any]], Any]) -> Callable[[dict[str, Any]], Any]:
            self._tools[name] = _Tool(
                name=name,
                description=description,
                schema={
                    "type": "object",
                    "properties": properties or {},
                    "required": required or [],
                },
                handler=handler,
            )
            return handler

        return register

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    # ---- the tool-provider contract ----

    def descriptors(self) -> list[dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "inputSchema": t.schema}
            for t in self._tools.values()
        ]

    def call(self, name: str, args: dict[str, Any] | None = None) -> tuple[str, bool]:
        """Returns ``(text, is_error)``.

        Raises ``KeyError`` for an unknown tool so the server reports it as a
        protocol error rather than a tool result.
        """
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"unknown tool: {name}")

        try:
            return str(tool.handler(args or {})), False
        except self._rescuable as e:
            return f"error: {e}", True
