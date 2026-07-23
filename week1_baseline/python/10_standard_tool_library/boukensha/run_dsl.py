"""Port of ``lib/boukensha/run_dsl.rb``.

``RunDSL`` is the object handed to the ``setup`` callable of :func:`boukensha.run`.
It exposes only ``tool``, keeping the DSL surface intentionally small.

Ruby rebinds ``self`` to a ``RunDSL`` via ``instance_eval(&block)`` so a bare
``tool "..."`` resolves against it. Python has no ``instance_eval``; the faithful
equivalent is a ``setup`` callable that receives the ``RunDSL`` explicitly::

    def setup(t):
        @t.tool("read_file", description="...", parameters={"path": {...}})
        def read_file(path: str) -> str:
            ...

    boukensha.run(task="...", setup=setup)
"""

from __future__ import annotations

from typing import Any, Callable

from boukensha.registry import Registry


class RunDSL:
    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def tool(
        self, name: str, *, description: str, parameters: dict[str, Any] | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self._registry.tool(name, description=description, parameters=parameters)
