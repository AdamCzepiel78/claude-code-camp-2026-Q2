# 06 · The Logger (Python port)

Python 3 port of [`ruby/06_the_logger`](../../ruby/06_the_logger/README.md). Same design — see
the Ruby README for the full considerations. This document covers the Python-specific
implementation and how it differs from the Ruby source.

Step 5 printed its progress with `print()` — transient and unstructured. Step 6 replaces that
with a **structured JSONL logger**: every phase of a turn is written as one JSON object per line
to `.boukensha/sessions/<session-id>.jsonl`, appended and flushed immediately.

## New file (vs. step 5)

| File | Purpose |
|---|---|
| `boukensha/logger.py` | `Logger` — writes one JSON event per line to a session file |

## `boukensha.logger.Logger`

`Logger(*, session_id=None, dir=None, log=None, snapshot=None)` opens (append mode) a file at
`dir/<session-id>.jsonl` — `dir` defaults to `boukensha.config().dir / "sessions"` — and writes a
`session_start` line. Each method below writes one line, always carrying `session_id` and an ISO
`at` timestamp:

| Method | `phase` |
|---|---|
| `iteration(n, max)` | `iteration` |
| `prompt(messages, tools)` | `prompt` |
| `response(text, usage, stop_reason, task, backend)` | `response` (+ token/cost metadata) |
| `tool_call(name, args)` | `tool_call` |
| `tool_result(name, result, ok, error)` | `tool_result` |
| `limit_reached(kind, n, max)` | `limit_reached` |
| `turn_end(reason, iterations, tokens)` | `turn_end` |
| `raw(data)` | `raw` — only when `boukensha.debug()` |

A `response` line is enriched with `task`, `provider`, `model`, `usage_unit`, `usage_level`,
`input_tokens`, `output_tokens`, and `cost_usd`. Token counts are read robustly across provider
shapes (`input_tokens` / `prompt_tokens` / `promptTokenCount` / `prompt_eval_count`, and the
output equivalents), and `cost_usd` comes from `backend.estimate_cost(...)` — `0.0` for local
Ollama models.

## How the `Agent` uses it

- The constructor takes `logger=None` and defaults to a fresh `Logger()`.
- The two `print()` calls are gone: the loop now emits `iteration` + `prompt` events, plus a
  `raw` event (debug-only) for each response.
- Every exit path (completed / wind-down / fallback) logs a `response` and a `turn_end`.
- **Tool execution is fault-tolerant.** `registry.dispatch` is wrapped in `try/except Exception`;
  a failure is logged with `ok=False`, fed back to the model as `ERROR: <Type>: <msg>`, and the
  loop keeps going instead of crashing.

## What's different from the Ruby source

- **Module-level state.** Ruby's `Boukensha.config` / `debug?` / `quiet?` become module functions
  in `boukensha/__init__.py`: `config()` (memoized singleton), `set_debug()` / `debug()`,
  `set_quiet()` / `quiet()` — Python has no `?`/`!` method names.
- **Lazy import.** `logger.py` calls `import boukensha` *inside* `raw()` and `_default_dir()`
  rather than at module top, to avoid a circular import (the package `__init__` imports the
  logger).
- `PromptBuilder` gains a public `backend` property (Ruby's `attr_reader :backend`) so the agent
  can log model/usage/cost.
- Cleanup mirrored from Ruby: the unused `LoopError` is removed. `config.py` / `context.py` need
  no change (the Ruby edits there were cosmetic, and the Python `Config` already exposes `dir`).

## Running it

```
bin/06_the_logger_python   # from week1_baseline/
```

Prints only the header and the final response; the full trace lands in
`.boukensha/sessions/*.jsonl`. Run `bin/06_the_logger_ruby` for the byte-comparable Ruby run.
