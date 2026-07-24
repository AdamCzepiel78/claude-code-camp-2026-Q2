# Plan: Port `ruby/07_the_run_dsl` → `python/07_the_run_dsl`

Status: **planned, not yet implemented**
Date: 2026-07-22

## Scope

1. Port the Ruby `07_the_run_dsl` step into `week1_baseline/python/07_the_run_dsl`.
2. Add two launcher scripts:
   - `week1_baseline/bin/07_the_run_dsl_ruby`
   - `week1_baseline/bin/07_the_run_dsl_python`

## Strategy

Copy `python/06_the_logger` as the baseline, then apply the same deltas Ruby
applied going `06_the_logger → 07_the_run_dsl`. The step's whole point is a
single top-level entry point — `Boukensha.run` — that hides all the manual
plumbing (Context/Registry/backend/PromptBuilder/Client/Logger/Agent) behind one
call plus a small tool-declaration DSL.

What step 07 adds (from the Ruby `06 → 07` diff):
- New `lib/boukensha/run_dsl.rb` — `RunDSL`, a tiny host object exposing only
  `tool`.
- `lib/boukensha.rb` gains the `Boukensha.run(...)` factory that wires every
  primitive together, adds the user `task` message, runs the agent, and closes
  the logger in an `ensure`.
- `logger.rb` gains `turn(n:)` and a `subscribe(&block)` hook (subscribers are
  invoked on every logged event) — infrastructure the later REPL/TUI steps use.
- Cleanup churn mirrored from Ruby: `LoopError` re-added to `errors.rb`;
  `config.rb`/`context.rb` changes are cosmetic.

## The key design decision — Ruby `instance_eval` → Python `setup(dsl)`

Ruby's DSL relies on `RunDSL.new(registry).instance_eval(&block)`, which rebinds
`self` inside the block so a bare `tool "read_file", ...` resolves to
`RunDSL#tool`. Python has no `instance_eval`. The faithful, idiomatic equivalent
is a **`setup` callable that receives the `RunDSL`**:

```python
def setup(t):
    @t.tool("read_file", description="...", parameters={"path": {...}})
    def read_file(path: str) -> str:
        return ...

result = boukensha.run(task="...", setup=setup)
```

`RunDSL.tool` mirrors `Registry.tool` exactly (a decorator factory), so tools are
declared with the same `@t.tool(...)` decorator already used elsewhere in the
port. This keeps the DSL surface intentionally small (only `tool`) while reading
naturally in Python.

## New file

1. **`boukensha/run_dsl.py`** — port of `lib/boukensha/run_dsl.rb`.
   ```python
   class RunDSL:
       def __init__(self, registry: Registry) -> None: ...
       def tool(self, name, *, description, parameters=None):
           return self._registry.tool(name, description=description, parameters=parameters)
   ```

## Modified files (mirroring the Ruby `06 → 07` deltas)

2. **`boukensha/__init__.py`** — add the top-level `run(...)` function (Ruby's
   `Boukensha.run`) alongside the existing `config()`/`debug()`/`quiet()` state:
   - Signature:
     ```python
     def run(*, task, system=None, model=None, backend=None, api_key=None,
             ollama_host="http://localhost:11434", log=None,
             max_output_tokens=None, setup=None) -> str
     ```
   - Body mirrors the Ruby factory:
     1. `cfg = config()`; `task_class = Player`; `settings = cfg.tasks(task_class.task_name())`.
     2. Default `system`/`model`/`backend` from the task settings
        (`backend` from `provider`), matching Ruby's `||=` fallbacks.
     3. Resolve `api_key` from the matching env var per backend
        (`ANTHROPIC_/OPENAI_/GEMINI_/MAMMOUTH_/OLLAMA_API_KEY`), except `ollama`.
     4. Build `Context(task=task_class, system=system)` + `Registry`.
     5. `if setup is not None: setup(RunDSL(registry))`.
     6. Select the backend from `backend` (reuse the same provider→backend
        mapping the example already uses; `ollama` takes `host=ollama_host`).
     7. Build `PromptBuilder`, `Client`; compute `effective_max_iterations` /
        `effective_max_output_tokens`; build `Logger(log=log, snapshot={task,
        max_iterations, max_output_tokens, model, provider})`; build `Agent(...)`.
     8. `ctx.add_message("user", task)`; `try: return agent.run() finally: logger.close()`.
   - Import and export `RunDSL` and `run`; keep the existing exports.

3. **`boukensha/logger.py`**:
   - add `turn(self, *, n)` → writes `{"phase": "turn", "n": n}`.
   - add `subscribe(self, callback)` storing callbacks, and have `_write_log`
     invoke each subscriber with the event after writing it.

4. **`boukensha/errors.py`** — re-add `class LoopError(Exception)` (mirrors the
   Ruby churn) and re-export it from `__init__`.

5. **`boukensha/config.py`, `boukensha/context.py`** — no change needed. The Ruby
   deltas here were cosmetic (whitespace / re-adding `mud_*`, which the Python
   `Config` already has).

6. **`examples/example.py`** — rewrite around `boukensha.run`:
   - banner `=== BOUKENSHA Step 7: The Boukensha.run DSL ===` and `Config: {boukensha.config()!r}`.
   - define a `setup(t)` that registers `read_file` and `list_directory` (both
     resolving paths against `base_dir`, as in step 6) via `@t.tool(...)`.
   - `result = boukensha.run(task="Read the README.md file and summarise ...", setup=setup)`.
   - keep the `BOUKENSHA_DIR` default and the `sys.path.insert` shim.
   - print `=== FINAL RESPONSE ===` + result.

7. **`pyproject.toml`** — `name = "boukensha-the-run-dsl"`,
   `description = "... Step 7: The Run DSL (Python port)"`.

8. **`README.md`** — rewrite as the Step 7 port doc: the `run` entry point, the
   options table, the `RunDSL`/`setup(dsl)` adaptation of Ruby's `instance_eval`
   block, and the new `logger.turn`/`subscribe` hooks.

9. **`prompts/system.md`, `py.typed`** — carry forward unchanged (diff
   `system.md` 06→07 first; expected identical).

## bin scripts

10. **`bin/07_the_run_dsl_ruby`** — clone of `bin/06_the_logger_ruby`:
    `cd .../ruby/07_the_run_dsl && bundle exec ruby examples/example.rb`.

11. **`bin/07_the_run_dsl_python`** — clone of `bin/06_the_logger_python`: shared-venv
    bootstrap, then `exec .venv/bin/python 07_the_run_dsl/examples/example.py`.

Both scripts `chmod +x`.

## Verification

12. Byte-compile the package (`python -m compileall python/07_the_run_dsl/boukensha`).
13. Offline `run` check (no API keys): monkeypatch the client/agent path — or reuse
    the step-6 fake-client harness by calling `boukensha.run(..., setup=...)` with a
    stubbed backend — and assert:
    - the `setup(dsl)` callback registers both tools on the context,
    - the agent runs and returns the final text,
    - the session log opens with a `session_start` snapshot carrying
      `task`/`model`/`provider`/`max_iterations`/`max_output_tokens`,
    - the logger is closed afterward (file handle closed) even if `agent.run` raises.
14. Offline logger check: `subscribe(cb)` fires `cb` for every event; `turn(n=…)`
    writes a `turn` line.
15. Live side-by-side (needs Ollama + `.boukensha/settings.yaml`): run
    `bin/07_the_run_dsl_ruby` and `bin/07_the_run_dsl_python`, then compare the
    generated `.boukensha/sessions/*.jsonl` phase sequences and the snapshot line.
