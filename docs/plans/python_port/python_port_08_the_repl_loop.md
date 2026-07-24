# Plan: Port `ruby/08_the_repl_loop` → `python/08_the_repl_loop`

Status: **planned, not yet implemented**
Date: 2026-07-22

## Scope

1. Port the Ruby `08_the_repl_loop` step into `week1_baseline/python/08_the_repl_loop`.
2. Add two launcher scripts:
   - `week1_baseline/bin/08_the_repl_loop_ruby`
   - `week1_baseline/bin/08_the_repl_loop_python`

## Strategy

Copy `python/07_the_run_dsl` as the baseline, then apply the same deltas Ruby
applied going `07_the_run_dsl → 08_the_repl_loop`. Step 8 turns the one-shot
`run` into an interactive, multi-turn **REPL** (`Boukensha.repl`) whose `Context`
is shared across turns so conversation history accumulates.

What step 08 adds (from the Ruby `07 → 08` diff):
- New `lib/boukensha/repl.rb` — the interactive session loop with built-in
  commands.
- New `lib/boukensha/version.rb` — `VERSION = "0.8.0"`.
- `lib/boukensha.rb` gains the `Boukensha.repl(...)` factory (same as `run`,
  minus `task:`; builds a `Repl` and calls `.start`).
- `agent.rb` now **persists the final assistant reply into the context** so the
  next REPL turn sees it.
- `context.rb` gains `clear_messages!` (the `/clear` command).
- `client.rb` raises a friendly `ApiError` on HTTP 401.
- `config.rb` `resolve_dir` now also checks `./.boukensha` (cwd) before falling
  back to `~/.boukensha`.

## New files

1. **`boukensha/version.py`** — `VERSION = "0.8.0"`.

2. **`boukensha/repl.py`** — port of `lib/boukensha/repl.rb`. Class `Repl`:
   - `__init__(self, *, context, registry, builder, client, logger, config_dir=None,
     provider=None, model=None, version=None, api_key=None, task_settings=None,
     max_iterations=None, max_output_tokens=None)`.
   - `start()`:
     - print the banner (box with version, config dir + existence check, provider/model,
       API-key status, command hints).
     - loop: print `PROMPT` (`"boukensha> "`), read a line via `input()`.
       - **EOF (Ctrl-D)** → `input()` raises `EOFError` → break.
       - blank line → continue.
       - dispatch built-in commands: `/exit`|`/quit` → "Goodbye." + break;
         `/help` → print `HELP`; `/quiet` → `boukensha.set_quiet(True)`;
         `/loud` → `boukensha.set_quiet(False)`; `/clear` →
         `context.clear_messages()` + reset turn counter.
       - otherwise `run_turn(input)`.
   - `run_turn(text)`: increment turn, `logger.turn(n=…)`, `context.add_message("user", text)`,
     build a fresh `Agent(...)` with the shared context/logger, `agent.run()`,
     print the result (outside the logger so it shows even when quiet). Wrap in
     `try/except (LoopError, ApiError)` → print `[error] …`.
   - `PROMPT`, `HELP`, and the banner text mirror the Ruby constants.

   Python note: Ctrl-C (`KeyboardInterrupt`) is handled at the `repl()` factory
   level (Ruby rescues `Interrupt` there), matching the Ruby structure.

## Modified files (mirroring the Ruby `07 → 08` deltas)

3. **`boukensha/__init__.py`** — add the top-level `repl(...)` function:
   - Same signature as `run(...)` **minus `task`**, plus `setup`.
   - Body mirrors `run` up through building `ctx`/`registry`/`setup`/backend/
     `builder`/`client`/`effective_*`/`logger` (with the same `session_start`
     snapshot), then constructs a `Repl(...)` (passing `config_dir=cfg.dir`,
     `provider=backend`, `model`, `version=VERSION`, `api_key`, and the
     task/limit settings) and calls `.start()`.
   - Wrap in `try/except KeyboardInterrupt` (print `"\nInterrupted."`) and
     `finally: logger.close()` (Ruby's `rescue Interrupt` / `ensure`).
   - Import/export `Repl`, `repl`, and `VERSION`.

4. **`boukensha/agent.py`** — persist the final assistant reply to the context
   (so REPL turns accumulate history), at all three exit points that return text:
   - completed branch in `run()`: `self._context.add_message("assistant", text)`
     just before `return text`;
   - `_wrap_up` success: `self._context.add_message("assistant", text)` before returning;
   - `_wrap_up` `ApiError` fallback: `self._context.add_message("assistant", msg)` before returning.

5. **`boukensha/context.py`** — add `clear_messages(self)` that resets
   `self.messages = []` (Ruby's `clear_messages!`; Python drops the `!`).

6. **`boukensha/client.py`** — after the retry loop, if the response status is
   401, raise `ApiError("authentication failed (401) — check your API key")`
   before the generic non-2xx error.

7. **`boukensha/config.py`** — extend `_resolve_dir()`:
   1. `BOUKENSHA_DIR` if set;
   2. else `Path.cwd() / ".boukensha"` if it is a directory;
   3. else `DEFAULT_DIR` (`~/.boukensha`).

8. **`examples/example.py`** — rewrite around `boukensha.repl`:
   - print `Config: {boukensha.config()!r}`.
   - `base_dir` points at the sibling `07_the_run_dsl` package dir (a playground
     with real files to read), matching the Ruby example.
   - define `setup(t)` registering `read_file` / `list_directory`.
   - call `boukensha.repl(setup=setup)`.

9. **`pyproject.toml`** — `name = "boukensha-the-repl-loop"`,
   `description = "... Step 8: The REPL Loop (Python port)"`.

10. **`README.md`** — rewrite as the Step 8 port doc: the `repl` entry point and
    command table, shared-context multi-turn history, `agent` persisting replies,
    `Context.clear_messages`, the 401 handling, and the cwd config-dir lookup.
    Note the Python adaptations: `input()`/`EOFError` for Ctrl-D,
    `KeyboardInterrupt` for Ctrl-C, `set_quiet(True/False)` for `/quiet`/`/loud`.

11. **`prompts/system.md`, `py.typed`** — carry forward unchanged (diff
    `system.md` 07→08 first; expected identical).

Note: as in Ruby, `quiet()` is currently only *set* by `/quiet` (nothing reads it
to suppress file logging yet) — port it faithfully; it's infrastructure for later.

## bin scripts

12. **`bin/08_the_repl_loop_ruby`** — clone of `bin/07_the_run_dsl_ruby`:
    `cd .../ruby/08_the_repl_loop && bundle exec ruby examples/example.rb`.

13. **`bin/08_the_repl_loop_python`** — clone of `bin/07_the_run_dsl_python`: shared-venv
    bootstrap, then `exec .venv/bin/python 08_the_repl_loop/examples/example.py`.

Both scripts `chmod +x`.

## Verification

14. Byte-compile the package (`python -m compileall python/08_the_repl_loop/boukensha`).
15. Offline REPL check (no API keys, no real stdin): drive `Repl.start()` with a
    fake `sys.stdin` (e.g. `io.StringIO("/help\n/clear\n/exit\n")`) and a stubbed
    `Client.call`; assert:
    - `/help` prints the command list, `/clear` calls `context.clear_messages()`,
      `/exit` ends the loop, and EOF (empty `StringIO`) also ends it cleanly;
    - a normal input line runs a turn, logs a `turn` line, appends the user
      message, and prints the reply.
16. Offline multi-turn/history check: with a stubbed client returning a text reply,
    run two turns against one `Repl` and assert the context contains the first
    turn's user+assistant messages before the second turn runs (agent now persists
    the assistant reply) — and that `agent.run` returning also left the assistant
    message in `ctx.messages`.
17. Offline unit checks: `Context.clear_messages()` empties messages but keeps tools;
    `client` raises the friendly `ApiError` on a 401; `_resolve_dir` picks
    `./.boukensha` when present and no `BOUKENSHA_DIR`.
18. Live smoke (needs Ollama + `.boukensha`): pipe `"hi\n/exit\n"` into
    `bin/08_the_repl_loop_python`, confirm it prints the banner, a reply, and a
    session `*.jsonl` with a `turn` line; compare against `bin/08_the_repl_loop_ruby`.
