"""Port of ``lib/boukensha/registry.rb``.

The agent never calls a tool directly — it emits a structured request (name
+ args) and the ``Registry`` looks up the tool and runs it.
"""

from __future__ import annotations

from typing import Any, Callable

from boukensha.context import Context
from boukensha.errors import UnknownToolError
from boukensha.tool import Tool


class Registry:
    def __init__(self, context: Context) -> None:
        self._context = context

    def tool(
        self, name: str, *, description: str, parameters: dict[str, Any] | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator that registers ``func`` as a tool on the underlying context.

        Ruby's ``Registry#tool`` takes its callable as a trailing block; the
        Python equivalent for "metadata up front, function body after" is a
        decorator factory::

            @registry.tool("move", description="...", parameters={...})
            def move(direction: str) -> str:
                ...
        """

        def register(func: Callable[..., Any]) -> Callable[..., Any]:
            tool = Tool(name, description, parameters or {}, func)
            self._context.register_tool(tool)
            return func

        return register

    def dispatch(self, name: str, args: dict[str, Any] | None = None) -> Any:
        tool = self._context.tools.get(name)
        if tool is None:
            raise UnknownToolError(f"No tool registered as '{name}'")
        return tool.block(**(args or {}))
