"""Port of ``lib/boukensha/logger.rb``.

Structured session logging. Every phase of a turn is written as one JSON object
per line (JSONL) to ``.boukensha/sessions/<session-id>.jsonl`` — append-only and
flushed immediately, so a crash never loses what happened up to that point.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from boukensha.message import Message

DEFAULT_SESSION_DIR = "sessions"


class Logger:
    def __init__(
        self,
        *,
        session_id: str | None = None,
        dir: Path | str | None = None,
        log: Path | str | None = None,
        snapshot: dict[str, Any] | None = None,
    ) -> None:
        self.session_id = session_id or self._generate_session_id()
        base_dir = Path(dir) if dir is not None else self._default_dir()
        self.path = Path(log) if log is not None else base_dir / f"{self.session_id}.jsonl"

        self._subscribers: list[Any] = []
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._log_io = self.path.open("a", encoding="utf-8")
        self._write_log({"phase": "session_start", **(snapshot or {})})

    # ---------- event methods ------------------------------------------------

    def turn(self, *, n: int) -> None:
        self._write_log({"phase": "turn", "n": n})

    def iteration(self, *, n: int, max: int) -> None:
        self._write_log({"phase": "iteration", "n": n, "max": max})

    def limit_reached(self, *, kind: str, n: int, max: int) -> None:
        self._write_log({"phase": "limit_reached", "kind": kind, "n": n, "max": max})

    def turn_end(self, *, reason: str, iterations: int, tokens: Any = None) -> None:
        self._write_log(
            {"phase": "turn_end", "reason": reason, "iterations": iterations, "tokens": tokens}
        )

    def prompt(self, *, messages: list[Message], tools: dict[str, Any]) -> None:
        self._write_log(
            {
                "phase": "prompt",
                "message_count": len(messages),
                "messages": [self._serialize_message(m) for m in messages],
                "tool_count": len(tools),
                "tools": list(tools.keys()),
            }
        )

    def tool_call(self, *, name: str, args: Any) -> None:
        self._write_log({"phase": "tool_call", "name": name, "args": args})

    def tool_result(
        self, *, name: str, result: Any, ok: bool = True, error: str | None = None
    ) -> None:
        self._write_log(
            {"phase": "tool_result", "name": name, "result": str(result), "ok": ok, "error": error}
        )

    def response(
        self,
        *,
        text: Any,
        usage: dict[str, Any] | None = None,
        stop_reason: str | None = None,
        task: Any = None,
        backend: Any = None,
    ) -> None:
        self._write_log(
            {
                "phase": "response",
                "text": str(text).strip(),
                "usage": usage,
                "stop_reason": stop_reason,
                **self._execution_metadata(task=task, backend=backend, usage=usage),
            }
        )

    def raw(self, *, data: Any) -> None:
        import boukensha

        if not boukensha.debug():
            return
        self._write_log({"phase": "raw", "data": data})

    def subscribe(self, callback: Any) -> None:
        """Register a callback invoked with every logged event (after it is written)."""
        self._subscribers.append(callback)

    def close(self) -> None:
        if self._log_io is not None:
            self._log_io.close()

    # ---------- internals ----------------------------------------------------

    @staticmethod
    def _default_dir() -> Path:
        import boukensha

        return boukensha.config().dir / DEFAULT_SESSION_DIR

    def _write_log(self, event: dict[str, Any]) -> None:
        line = {**event, "session_id": self.session_id, "at": self._now_iso()}
        self._log_io.write(json.dumps(line) + "\n")
        self._log_io.flush()
        # Mirror Ruby: subscribers receive the original event (without the
        # session_id/at envelope added above).
        for subscriber in self._subscribers:
            subscriber(event)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now().astimezone().isoformat()

    @staticmethod
    def _generate_session_id() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)

    @staticmethod
    def _serialize_message(msg: Message) -> dict[str, Any]:
        return {"role": msg.role, "content": msg.content}

    def _execution_metadata(self, *, task: Any, backend: Any, usage: Any) -> dict[str, Any]:
        if not (task or backend or usage):
            return {}

        tokens = self._usage_tokens(usage)
        metadata = {
            "task": self._task_name(task),
            "provider": self._provider_name(backend),
            "model": getattr(backend, "model", None),
            "usage_unit": getattr(backend, "usage_unit", None),
            "usage_level": getattr(backend, "usage_level", None),
            "input_tokens": tokens["input"],
            "output_tokens": tokens["output"],
            "cost_usd": self._estimate_cost(backend, tokens),
        }
        return {k: v for k, v in metadata.items() if v is not None}

    @staticmethod
    def _task_name(task: Any) -> str | None:
        if task is None:
            return None
        return task.task_name() if hasattr(task, "task_name") else str(task)

    @staticmethod
    def _provider_name(backend: Any) -> str | None:
        if backend is None:
            return None
        name = type(backend).__name__
        return re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name).lower()

    def _usage_tokens(self, usage: Any) -> dict[str, int | None]:
        usage = usage or {}
        return {
            "input": self._first_integer(
                usage, "input_tokens", "prompt_tokens", "promptTokenCount", "prompt_eval_count"
            ),
            "output": self._first_integer(
                usage, "output_tokens", "completion_tokens", "candidatesTokenCount", "eval_count"
            ),
        }

    @staticmethod
    def _first_integer(mapping: dict[str, Any], *keys: str) -> int | None:
        for key in keys:
            value = mapping.get(key)
            if value is not None:
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return None
        return None

    @staticmethod
    def _estimate_cost(backend: Any, tokens: dict[str, int | None]) -> float | None:
        if backend is None or not hasattr(backend, "estimate_cost"):
            return None
        if tokens["input"] is None or tokens["output"] is None:
            return None
        return backend.estimate_cost(
            input_tokens=tokens["input"], output_tokens=tokens["output"]
        )
