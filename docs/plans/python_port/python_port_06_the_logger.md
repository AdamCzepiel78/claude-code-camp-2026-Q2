# Plan: Port `ruby/06_the_logger` → `python/06_the_logger`

Status: **planned, not yet implemented**
Date: 2026-07-22

## Scope

1. Port the Ruby `06_the_logger` step into `week1_baseline/python/06_the_logger`.
2. Add two launcher scripts:
   - `week1_baseline/bin/06_the_logger_ruby`
   - `week1_baseline/bin/06_the_logger_python`

## Strategy

Copy `python/05_agent_loop` as the baseline, then apply the same deltas Ruby
applied going `05_agent_loop → 06_the_logger`. The only new concept in this step
is a structured **JSONL session logger**; everything else is wiring it in.

What step 06 adds (from the Ruby `05 → 06` diff):
- New `lib/boukensha/logger.rb` — writes one JSON object per line to
  `.boukensha/sessions/<session-id>.jsonl`.
- The agent logs every phase (iteration, prompt, response, tool_call,
  tool_result, limit_reached, turn_end) instead of `puts`-ing to the terminal.
- Tool execution becomes fault-tolerant (exceptions are caught, logged with
  `ok: false`, and fed back to the model as `ERROR: ...`).
- Module-level state on `Boukensha` (`config`, `quiet!`/`quiet?`,
  `debug!`/`debug?`); `debug?` gates the `raw` (full response) log line.
- `PromptBuilder` exposes its `backend` so the agent can log model/usage/cost.
- Cleanup: unused `LoopError` removed; `config.rb`/`context.rb` whitespace only.

## New file

1. **`boukensha/logger.py`** — port of `lib/boukensha/logger.rb`.

   Class `Logger`:
   - `__init__(self, *, session_id=None, dir=None, log=None, snapshot=None)`:
     resolve `session_id` (`<UTC-timestamp>-<hex>`), resolve `path`
     (`dir or default_dir()/f"{session_id}.jsonl"`), `mkdir -p` its parent,
     open the file in append mode, and write a `session_start` event merged with
     `snapshot`.
   - Event methods, each writing one line via `_write_log`:
     `iteration(n, max)`, `limit_reached(kind, n, max)`,
     `turn_end(reason, iterations, tokens=None)`,
     `prompt(messages, tools)`, `tool_call(name, args)`,
     `tool_result(name, result, ok=True, error=None)`,
     `response(text, usage=None, stop_reason=None, task=None, backend=None)`,
     `raw(data)` — returns early unless `boukensha.debug()`.
   - `close(self)` — close the file handle.
   - Internals:
     - `_write_log(event)`: `json.dumps(event | {"session_id": ..., "at": <iso8601>})`
       + `"\n"`, then `flush()`.
     - `_generate_session_id()`: `datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")`
       + `secrets.token_hex(4)`.
     - `_default_dir()`: `boukensha.config().dir / "sessions"` (lazy `import boukensha`
       inside the method to avoid a circular import — see module-state note below).
     - `_serialize_message(msg)`: `{"role": msg.role, "content": msg.content}`.
     - `_execution_metadata(task, backend, usage)`: builds
       `{task, provider, model, usage_unit, usage_level, input_tokens,
       output_tokens, cost_usd}` and drops `None` values (dict comprehension in
       place of Ruby's `.compact`).
     - `_usage_tokens(usage)`: first-present of
       `input_tokens|prompt_tokens|promptTokenCount|prompt_eval_count` and
       `output_tokens|completion_tokens|candidatesTokenCount|eval_count`.
     - `_provider_name(backend)`: camel→snake of `type(backend).__name__`
       (e.g. `OllamaCloud` → `ollama_cloud`).
     - `_estimate_cost(backend, tokens)`: call `backend.estimate_cost(...)` when
       both token counts are present (`Base.estimate_cost` already exists).

   Python idiom note: Ruby `Time.now.iso8601` → `datetime.now().astimezone().isoformat()`.

## Modified files (mirroring the Ruby `05 → 06` deltas)

2. **`boukensha/__init__.py`** — add module-level state mirroring `Boukensha`'s
   class methods:
   - a cached `config()` (module-global `_config`, lazily `Config()`),
   - `set_quiet(bool)` / `quiet()`, `set_debug(bool)` / `debug()`
     (Python has no `?`/`!` method names; use plain accessors).
   - Export `Logger`; import it and `backends.base` so they load with the package.
   Keep `Agent` etc. exports.

3. **`boukensha/agent.py`** — integrate the logger (largest diff):
   - `__init__(..., logger: Logger | None = None)`; default to `Logger()`.
   - Replace the two `print()` calls with
     `self._logger.iteration(n=…, max=…)` and
     `self._logger.prompt(messages=self._context.messages, tools=self._context.tools)`;
     add `self._logger.raw(data=response)` after each call.
   - On limit: `self._logger.limit_reached(kind="max_iterations", …)` before `wrap_up`.
   - On every exit path (completed / wrap-up / fallback) call `log_response(...)`
     and `self._logger.turn_end(reason=…, iterations=self._iteration)`.
   - `handle_tool_calls(content, response)`:
     - log the assistant reasoning (or a `"(tool use — N calls)"` placeholder) via
       `log_response`,
     - wrap `registry.dispatch` in `try/except Exception`: on success
       `tool_result(ok=True)`; on failure set `result = f"ERROR: {type(e).__name__}: {e}"`
       and `tool_result(ok=False, error=str(e))`, then still feed `result` back as a
       `tool_result` message.
   - New helpers `log_response(text, response)` and `normalized_usage(response)`
     (`usage` → `usageMetadata` → `{prompt_eval_count, eval_count}` → None).
   - `log_response` reads the backend via `self._builder.backend` (next item).

4. **`boukensha/prompt_builder.py`** — add a public `backend` property returning
   `self._backend` (Ruby added `attr_reader :backend`).

5. **`boukensha/errors.py`** — remove `LoopError` (mirrors the Ruby cleanup) and
   drop it from `__init__`'s exports.

6. **`boukensha/config.py`, `boukensha/context.py`** — no change needed. The Ruby
   deltas here were cosmetic; the Python `Config` already exposes `self.dir` and
   already keeps the `mud_*` accessors.

7. **`examples/example.py`** — build `logger = Logger()`, pass `logger=logger` to
   the `Agent`, change the banner to `=== BOUKENSHA Step 6: The Logger ===`, and add
   the comment about `boukensha.set_debug(True)` enabling the raw response lines.
   (The per-iteration/tool output now goes to the JSONL file, not stdout — only the
   header and `=== FINAL RESPONSE ===` remain on the terminal, same as Ruby.)

8. **`pyproject.toml`** — `name = "boukensha-the-logger"`,
   `description = "... Step 6: The Logger (Python port)"`.

9. **`README.md`** — rewrite as the Step 6 port doc: the JSONL logger, the phases
   table, the fault-tolerant tool execution, the module-level `config/debug/quiet`
   state, and how it differs from the Ruby source (accessor naming, lazy import to
   avoid the circular dependency).

10. **`prompts/system.md`, `py.typed`** — carry forward unchanged (diff
    `system.md` 05→06 first; it is expected to be identical).

## bin scripts

11. **`bin/06_the_logger_ruby`** — clone of `bin/05_agent_loop_ruby`:
    `cd .../ruby/06_the_logger && bundle exec ruby examples/example.rb`.

12. **`bin/06_the_logger_python`** — clone of `bin/05_agent_loop_python`: shared-venv
    bootstrap (installs only `python-dotenv` + `PyYAML`), then
    `exec .venv/bin/python 06_the_logger/examples/example.py`.

Both scripts `chmod +x`.

## Verification

13. Byte-compile the package (`python -m compileall python/06_the_logger/boukensha`).
14. Offline logger unit check (no API keys): construct a `Logger(dir=<tmp>)`, emit one
    of each event, then read the file back and assert every line is valid JSON, carries
    `session_id`/`at`/`phase`, and that a `response` event with a fake Ollama `usage`
    (`prompt_eval_count`/`eval_count`) yields `input_tokens`/`output_tokens` and
    `cost_usd == 0.0` for the local backend.
15. Offline agent check: reuse the `05` fake-client/fake-builder harness with a
    `Logger(dir=<tmp>)`; assert the loop still returns the final text and that the log
    contains `iteration`, `prompt`, `tool_call`, `tool_result`, `response`, `turn_end`
    lines — and that a raising tool produces a `tool_result` with `ok: false` while the
    loop continues.
16. Live side-by-side (needs Ollama + `.boukensha/settings.yaml`): run
    `bin/06_the_logger_ruby` and `bin/06_the_logger_python`, then compare the two
    generated `.boukensha/sessions/*.jsonl` files for matching phase sequences.
