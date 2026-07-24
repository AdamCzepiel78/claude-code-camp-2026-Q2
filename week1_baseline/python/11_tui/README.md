# 11 · A Terminal UI (Python port)

Python 3 port of [`ruby/11_tui`](../../ruby/11_tui/README.md). Same design —
see the Ruby README for the full feature narrative and the keyboard-shortcut
table (unchanged). This document covers the Python-specific implementation.

Everything from [step 10](../10_standard_tool_library/README.md) — the
standard tool library, `boukensha.mcp`, MUD tools via `mud_manager_mcp` by
default, config-driven `mcp_servers:` — carries forward unchanged. Step 11
adds a full terminal UI on top, wrapping the plain REPL in a structured
four-zone display: a scrollable conversation log, a live progress line, an
input box, and a status bar. `tui=False` (or the `--no-tui` CLI flag) falls
back to the plain REPL, byte-for-byte the same as step 10.

## What's new

### `boukensha.tui` — built on Textual, not a `charm` port

Ruby's `Boukensha::Tui` is built on [`charm`](https://github.com/charm-ruby/charm),
Ruby bindings over the Go `bubbletea`/`lipgloss`/`bubbles` libraries. There is
no Python equivalent gem to bind against, so this is a **port to a different
toolkit** — [Textual](https://textual.textualize.io/) — rather than a
line-for-line translation. One library covers everything bubbletea (event
loop) + lipgloss (styling) + bubbles (widgets) covered together, including a
`@work(thread=True)` decorator that is the natural stand-in for Ruby's
`Thread.new { @repl.run_turn(input) }` + manual `Queue` draining: Textual's
`call_from_thread` already provides the thread-safe hop back onto the UI
event loop, so there is no hand-rolled event queue here.

This is the first non-stdlib, non-`python-dotenv`/`PyYAML` runtime dependency
in the Python port series — accepted deliberately, the same way those two
were: the stdlib doesn't cover a real terminal UI, and building the four-zone
reactive layout on raw `curses` instead would mean hand-rolling a scrollable
viewport, spinner timing, and non-blocking input from scratch.

```python
import boukensha
boukensha.repl()                # Textual TUI (default)
boukensha.repl(tui=False)       # plain terminal REPL, same as step 10
```

### `boukensha.repl.Repl` refactored for composability

`Repl` no longer hard-codes `print`/`input`. Three entry points let a
different front-end drive it — `boukensha.tui.BoukenshaApp` is one, but
nothing here is TUI-specific:

| Method | Purpose |
|---|---|
| `on_output(callback)` | Route all output through `callback` instead of stdout |
| `handle_command(text)` | Process a slash command; returns `"quit"`, `"command"`, or `None` |
| `run_turn(text)` | Run one agent turn and route the result through the callback |

`logger`, `context`, `model`, `version`, and `banner()` are public for the
same reason — the TUI's status line and startup log need them.

### `/quiet` and `/loud` removed

Both the REPL commands and the underlying `boukensha.set_quiet`/`quiet()`
module functions are gone — mirroring Ruby's `11_tui`, which dropped
`Boukensha.quiet!`/`loud!`/`quiet?` entirely. In both languages this toggle
was already dead by step 10: nothing anywhere read the flag it set (the JSONL
logger replaced the verbose-stdout-logging it once gated), so removing it in
this step is a real cleanup, not a regression — confirmed by grepping both
codebases for any remaining read of the flag.

### Interrupt (`Esc`) — a documented limitation, not a gap

Ruby's `Esc` handler can abort a blocking HTTP call mid-flight because MRI
delivers an async-raised exception at the next I/O interrupt point
(`Thread#raise`). Python threads have no safe equivalent — the nearest
mechanism (`ctypes`-based async exception injection) only takes effect at the
next bytecode boundary, which for a blocking `socket.recv()` is no earlier
than when the call already returns, so it buys nothing over a plain flag
while adding real risk.

So here, `Esc` marks the turn's run id stale and returns control to the UI
immediately. The background thread's in-flight HTTP call keeps running to
completion (typically a few seconds) and its result is silently discarded
when it calls back. From the user's perspective the UI unblocks right away —
the request isn't aborted early, only its result is ignored. See the
docstring in `boukensha/tui.py` for the full reasoning.

### Layout: no manual resize handling

Ruby's `Tui` tracks terminal width/height itself and re-renders a joined
string on every message (bubbletea's lower-level model). Textual's CSS
layout (`compose()` + the `CSS` class attribute) resizes the four zones
automatically, so there's no `on_resize` handler in the Python port — one of
the genuine simplifications the higher-level toolkit buys over a line-for-line
port.

## Run the demo

```sh
python examples/example.py     # step-10 MUD demo, unchanged — doesn't exercise the TUI

# or via the global executable pointed at this step:
BOUKENSHA_PATH=~/…/python/11_tui boukensha           # Textual TUI
BOUKENSHA_PATH=~/…/python/11_tui boukensha --no-tui  # plain REPL
```

`examples/example.py` is carried over unchanged from step 10 — it's the MUD
demo, and it doesn't exercise the TUI, matching the Ruby README's own note
that the TUI is interactive and run via the global executable, not the
example script.

## Install

```sh
pip install "textual>=8.0"
```

Everything else needed is already a dependency from step 10
(`python-dotenv`, `PyYAML`).
