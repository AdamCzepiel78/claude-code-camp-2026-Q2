# 07 · The Run DSL (Python port)

Python 3 port of [`ruby/07_the_run_dsl`](../../ruby/07_the_run_dsl/README.md). Same design — see
the Ruby README for the full considerations. This document covers the Python-specific
implementation and how it differs from the Ruby source.

Every earlier step wired a `Context`, `Registry`, backend, `PromptBuilder`, `Client`, `Logger`,
and `Agent` by hand. Step 7 hides all of that behind a single call — `boukensha.run(...)` — plus a
tiny tool-declaration DSL.

```python
import boukensha

def setup(t):
    @t.tool("read_file", description="Read a file",
            parameters={"path": {"type": "string", "description": "File path"}})
    def read_file(path: str) -> str:
        return open(path).read()

result = boukensha.run(task="Summarise README.md", setup=setup)
```

## New file (vs. step 6)

| File | Purpose |
|---|---|
| `boukensha/run_dsl.py` | `RunDSL` — the object handed to `setup`, exposing only `tool` |

## `boukensha.run(...)`

| Option | Default | Description |
|---|---|---|
| `task` | *(required)* | The user message handed to the agent |
| `system` | task's `system_prompt` | System prompt |
| `model` | task's `model` | Model name |
| `backend` | task's `provider` | `anthropic` / `openai` / `gemini` / `mammouth` / `ollama` / `ollama_cloud` |
| `api_key` | matching `*_API_KEY` env var | API key (not needed for `ollama`) |
| `ollama_host` | `http://localhost:11434` | Ollama base URL |
| `log` | `None` | JSONL path override (default `.boukensha/sessions/<id>.jsonl`) |
| `max_output_tokens` | task's `max_output_tokens` | Per-reply output cap |
| `setup` | `None` | Callable receiving a `RunDSL` to declare tools |

`run` loads config, resolves the defaults from the `player` task settings, builds every primitive,
opens a `Logger` whose `session_start` snapshot records `task`/`model`/`provider`/`max_iterations`/
`max_output_tokens`, runs the agent, and closes the logger in a `finally` (Ruby's `ensure`).

## The key difference from Ruby — `instance_eval` → `setup(dsl)`

Ruby's DSL uses `RunDSL.new(registry).instance_eval(&block)`, which rebinds `self` inside the block
so a bare `tool "..."` resolves against the `RunDSL`. Python has no `instance_eval`; the faithful,
idiomatic equivalent is a **`setup` callable that receives the `RunDSL` explicitly**. `RunDSL.tool`
mirrors `Registry.tool` (a decorator factory), so tools are declared with the same `@t.tool(...)`
decorator used elsewhere in the port, and the DSL surface stays intentionally small (only `tool`).

## Other changes carried over from Ruby

- `Logger` gains `turn(n)` and `subscribe(callback)`; `_write_log` now invokes each subscriber with
  the original event (matching Ruby, i.e. without the `session_id`/`at` envelope). These are
  infrastructure for the later REPL/TUI steps.
- `LoopError` is re-added to `errors.py`.
- `config.py` / `context.py` need no change (the Ruby edits there were cosmetic).

## Running it

```
bin/07_the_run_dsl_python   # from week1_baseline/
```

Prints only the header and the final response; the full trace lands in
`.boukensha/sessions/*.jsonl`. Run `bin/07_the_run_dsl_ruby` for the byte-comparable Ruby run.
