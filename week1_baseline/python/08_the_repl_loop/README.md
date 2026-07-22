# 08 · The REPL Loop (Python port)

Python 3 port of [`ruby/08_the_repl_loop`](../../ruby/08_the_repl_loop/README.md). Same design — see
the Ruby README for the full considerations. This document covers the Python-specific
implementation and how it differs from the Ruby source.

Step 7's `boukensha.run` runs one task and returns. Step 8 adds `boukensha.repl` — an interactive
loop that stays alive, reading tasks from stdin and running the agent turn after turn. The
`Context` is shared across turns, so **conversation history accumulates**: the agent sees the full
transcript every time.

|  | `run` | `repl` |
|---|---|---|
| Turns | one | many |
| History | discarded | accumulates across turns |
| User interaction | none | stdin prompt |

## New files (vs. step 7)

| File | Purpose |
|---|---|
| `boukensha/repl.py` | `Repl` — the interactive session loop + built-in commands |
| `boukensha/version.py` | `VERSION = "0.8.0"` |

## `boukensha.repl(...)`

Same options as `run`, **minus `task`** (the user supplies tasks interactively). Register tools in
the `setup` callback; then the loop takes over. Built-in commands (not sent to the agent):

| Command | Effect |
|---|---|
| `/quiet` | Suppress logging output (`set_quiet(True)`) |
| `/loud` | Re-enable it (`set_quiet(False)`) |
| `/clear` | Wipe conversation history (tools stay registered) |
| `/help` | Print the command list |
| `/exit` / `/quit` | Leave the REPL |
| Ctrl-D | EOF — leave the REPL |
| Ctrl-C | Interrupt — leave gracefully |

## Changes carried over from Ruby

- **`Agent` persists the final reply.** The agent now appends the final assistant text to the
  context at every exit path (completed / wind-down / fallback). One-shot `run` throws the context
  away, but the REPL needs the full transcript so the next turn sees the prior exchange.
- **`Context.clear_messages()`** wipes history while keeping tools/system prompt (Ruby's
  `clear_messages!`; Python drops the `!`). Used by `/clear`.
- **`Client`** raises a friendly `ApiError("authentication failed (401) …")` on HTTP 401.
- **`Config._resolve_dir`** now checks, in order: `BOUKENSHA_DIR`, then `./.boukensha` in the
  current working directory, then `~/.boukensha`.

## Python-specific adaptations

- Terminal I/O: `input()` for the prompt; **Ctrl-D** surfaces as `EOFError` (handled in the loop),
  **Ctrl-C** as `KeyboardInterrupt` (handled in the `repl()` factory, like Ruby's `rescue Interrupt`).
- `/quiet` / `/loud` map to `boukensha.set_quiet(True/False)`.
- As in Ruby, `quiet()` is currently only *set* — nothing reads it yet to suppress file logging;
  it's ported faithfully as infrastructure for later steps.
- `repl.py` does `import boukensha` at module top but only touches `boukensha.set_quiet` at
  call-time, so the package/`repl` circular import resolves cleanly.

## Running it

```
bin/08_the_repl_loop_python   # from week1_baseline/
```

Prints a banner, then a `boukensha> ` prompt. Try `list the files in .` then `read README.md`.
Each turn's trace lands in `.boukensha/sessions/*.jsonl` (with a `turn` line per turn). Run
`bin/08_the_repl_loop_ruby` for the byte-comparable Ruby REPL.
