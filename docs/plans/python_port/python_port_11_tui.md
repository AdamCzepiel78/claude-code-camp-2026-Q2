# Plan: Port `ruby/11_tui` → `python/11_tui`

Status: **implemented and extensively verified** (see "Outcome" below)
Date: 2026-07-25

## Scope

Port the Ruby `11_tui` step into `week1_baseline/python/11_tui`, plus a launcher
script `week1_baseline/bin/11_tui_python` alongside the (also new)
`bin/11_tui_ruby`.

This is the first step with a real terminal UI. Ruby wraps `Repl` in
`Boukensha::Tui`, built on the [`charm`](https://github.com/charm-ruby/charm)
gem — Ruby bindings over the Go `bubbletea`/`lipgloss`/`bubbles` libraries
(precompiled native extensions). Everything else — `Agent`, `Client`,
`Registry`, `Context`, the standard tool library, `Boukensha::MCP`,
`mud_manager_mcp` integration — is **unchanged** from step 10; step 11 is
additive.

## Outcome — 2026-07-25

Implemented at `week1_baseline/python/11_tui/` (seeded from `python/10_standard_tool_library`)
plus `bin/11_tui_python` and `bin/11_tui_ruby`. Both decisions from "Decisions
needed before starting" were resolved during implementation:

- **Esc-interrupt**: no plumbing added to `agent.py`/`client.py` (kept step 11
  additive, as scoped). `Esc` bumps a `run_id` and returns control to the UI
  immediately; the background thread's in-flight call keeps running to
  completion and its result is discarded on callback via a stale-`run_id`
  check. Documented in `boukensha/tui.py`'s module docstring and the README.
- **Textual version floor**: `textual>=8.0`, pinned against the real installed
  `8.2.8` in this environment — the plan's original `>=0.60` guess (written
  before any installation) would have been misleading; corrected once the
  actual API was verified by introspection (`from textual import work`, not
  `textual.worker.work`; `RichLog`/`Input`/`call_from_thread`/`set_interval`
  all confirmed against the real 8.x signatures before writing any code).

**A real bug was found and fixed during testing, not just during writing.**
`Repl.on_output`/`Logger.subscribe` callbacks fire from *two different
threads* depending on the call path: from the worker thread during a live
turn (`run_turn` inside `@work(thread=True)`), but directly on the **UI**
thread when a slash command is dispatched from a key binding (e.g. `Ctrl+L` →
`action_clear` → `handle_command("/clear")`). The first cut of `tui.py`
unconditionally called `self.call_from_thread(...)` in both cases — Textual
raises `RuntimeError: call_from_thread must run in a different thread from
the app` when that method is called while already on the UI thread. Fixed by
checking `get_current_worker()`/`NoActiveWorker` (Textual's sanctioned way to
ask "am I in a worker") and dispatching directly when already on the UI
thread. Caught by the headless `run_test()` smoke test, not by review — see
"Verification — results" below.

**A second finding, not a bug**: the live progress/status line's token
counters read `event["usage"]["input_tokens"]`/`["output_tokens"]` directly.
Anthropic's raw usage dict happens to use those key names; mammouth's is
OpenAI-shaped (`prompt_tokens`/`completion_tokens`), so the live *display*
silently stays at 0 for that backend. Checked against Ruby: `tui.rb:289` does
the exact identical nested read — this is a pre-existing quirk in the source
being ported, faithfully reproduced, not introduced by the port. The JSONL
log's separately-normalized top-level `input_tokens`/`output_tokens` fields
(computed by `Logger.execution_metadata`) are unaffected; this is a
display-only quirk in both languages.

`boukensha.set_quiet`/`quiet()` were removed **entirely** from
`boukensha/__init__.py`, not just from the REPL commands — the plan's draft
text had said the module function "stays... still used elsewhere," which
turned out to be wrong once checked: nothing in either the Python or the Ruby
codebase ever reads the flag it sets (dead since the JSONL logger replaced
verbose stdout logging), matching Ruby `11_tui`'s full removal exactly.

Two launcher-script bugs were caught and fixed during verification, not
before: both `bin/11_tui_python` and `bin/11_tui_ruby`'s `exec` lines were
missing `"$@"`, so `--no-tui` could never reach the loader through the actual
launcher — only through a hand-invoked `python -c "..."`. Found by running
the real scripts, not by re-reading the plan text.

## TUI library: Textual (decided)

`charm` has no Python equivalent — it's a Ruby-specific native wrapper around
Go libraries. Porting `Boukensha::Tui` line-for-line is not possible; a
different Python TUI toolkit has to stand in for bubbletea+lipgloss+bubbles
together. This mirrors the judgment call already made for `mud_manager`'s
`Session` (concurrency primitives are ported to idiomatic Python, not
transliterated) — same principle, applied to the UI layer.

**Decision: [Textual](https://textual.textualize.io/).** Reactive widgets, an
async app loop, a built-in `Input`, a scrollable log/viewport widget, CSS-like
styling, and a documented **threaded worker** API (`@work(thread=True)`) for
running blocking calls off the event loop. One library covers everything
`bubbletea` (event loop) + `lipgloss` (styling) + `bubbles` (widgets) cover
together — the closest one-to-one stand-in available, and the de facto
standard for this kind of app in Python today.

This is a new runtime dependency (`textual`, which pulls in `rich`) — the
first non-stdlib, non-`python-dotenv`/`PyYAML` dependency in the Python port
series. Accepted deliberately: the bootcamp has already taken on real
dependencies where the stdlib genuinely doesn't cover the need, and a terminal
UI is the same kind of case. Building the four-zone reactive dashboard on raw
`curses` instead would mean hand-rolling a scrollable viewport, spinner
timing, and non-blocking input from scratch — re-deriving what
`bubbletea`/`lipgloss`/`bubbles` already solved, the same trap the
`mud_manager_mcp` extraction work deliberately avoided elsewhere. Textual's
threaded-worker primitive is also the natural replacement for Ruby's
`Thread.new { @repl.run_turn(input) }` + `Queue`-based event relay — see
below.

### `--no-tui` fallback stays cheap either way

Every candidate is additive on top of the plain REPL from step 10, which
already exists in `python/10_standard_tool_library/boukensha/repl.py` and
needs no TUI library. `--no-tui` / `tui=False` importing the TUI module is
therefore optional and can fail gracefully (see `boukensha/tui.py` below) —
nobody who only wants the plain REPL needs the new dependency installed.

## Architecture mapping (Ruby → Python)

| Ruby (`bubbletea` Model protocol)                                                                                            | Python (Textual)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Tui#init` (initial model + first command)                                                                                   | `Tui.compose()` / `on_mount()`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `Tui#update(msg)` (message dispatch: resize, tick, key)                                                                      | Textual's built-in message system —`on_resize`, a `set_interval()` timer callback, `on_key` / `BINDINGS` + `action_*` methods                                                                                                                                                                                                                                                                                                                                                                                                    |
| `Tui#view` (render four zones, joined by `\n`)                                                                             | `compose()` yields child widgets laid out via Textual CSS (a `VerticalScroll`/log widget, a progress `Static`, an `Input`, a status `Static`), each updated independently instead of re-joining strings every frame                                                                                                                                                                                                                                                                                                               |
| `TickMsg` every 60 ms (spinner frame + elapsed time)                                                                         | `self.set_interval(0.06, self._tick)`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `@viewport` (`Bubbles::Viewport`, scrollable)                                                                              | Textual's`RichLog` (or a `VerticalScroll` containing `Static` lines) — has built-in scroll-to-bottom and `PageUp`/`PageDown` handling                                                                                                                                                                                                                                                                                                                                                                                            |
| `@textarea` (`Bubbles::TextArea`, single line, placeholder)                                                                | Textual's`Input` widget (`placeholder=`, `.value`, `.focus()`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `lip(...)` / `Lipgloss::Style` (fg/bg/bold)                                                                                | Textual CSS (`.styles.color`, `.styles.background`, `.styles.bold`) or Rich markup strings, since Textual renders Rich text natively                                                                                                                                                                                                                                                                                                                                                                                                  |
| `Thread.new { @repl.run_turn(input) }` + `Queue` of events, drained on each `TickMsg`                                    | `@work(thread=True)` worker method calling the blocking `repl.run_turn(input)`; `Logger.subscribe` callback uses `self.call_from_thread(self._handle_event, event)` to hand events back to the UI thread directly — no manual queue/poll loop needed, since Textual's worker API already provides the thread-safe handoff                                                                                                                                                                                                          |
| `handle_key` (`ctrl+c`/`ctrl+d` quit, `esc` interrupt, `ctrl+l` clear, `pgup`/`pgdown` scroll, `enter` submit) | Textual`BINDINGS` list + `action_quit`/`action_interrupt`/`action_clear`/`action_scroll_up`/`action_scroll_down`; `Input.Submitted` message for enter                                                                                                                                                                                                                                                                                                                                                                         |
| `@turn_thread.raise(Interrupt)` on `esc`                                                                                   | Threads can't be async-interrupted the way Ruby's`Thread#raise` can. Use a `threading.Event` (`self._interrupt_flag`) checked at the same points `Agent`/`Client` already check for cooperative cancellation, **or** — if no such checkpoint exists yet — document this as a known behavioural gap (`esc` requests interruption but the running HTTP call can't be aborted mid-flight) rather than silently no-op. Needs a decision (see below) once `agent.py`/`client.py` are inspected for a cancellation point. |

The event-driven architecture (background thread posting structured events,
UI thread draining them on a tick) is preserved conceptually; the mechanism
changes because Textual already solves thread → UI-thread handoff, which
Ruby's bubbletea binding does not.

## Behavioural deltas already present in `ruby/11_tui` (from the `10 → 11` Ruby diff)

Confirmed by diffing `ruby/10_standard_tool_library` against `ruby/11_tui`:

1. **`Boukensha::Tui`** — new class, described above.
2. **`Boukensha.repl` gains `tui:` kwarg** (default `true`). `tui: false` (or
   the `--no-tui` CLI flag) uses the plain REPL from step 10 unchanged.
3. **`Repl` refactored for composability** — no longer hard-codes
   `puts`/`gets`:
   - `on_output(&block)` routes all REPL output through a callback instead of
     `puts`, when set.
   - `handle_command(input)` — extracted from the inline `case` in `start`;
     returns `:quit`, `:command` (handled, don't run a turn), or `nil` (not a
     command, run it as a turn).
   - `run_turn(input)` — already private in step 10, promoted to public so
     `Tui` can drive it from a worker thread.
   - `logger`, `context`, `model`, `version` exposed as readers (Tui needs
     them for the status line).
4. **`/quiet` and `/loud` removed entirely** — both the REPL commands and the
   underlying `Boukensha.quiet!`/`loud!`/`quiet?` module methods are gone in
   `ruby/11_tui`. Confirmed by grep: zero references anywhere in `11_tui/lib`
   or its `README.md`. The Python port's `boukensha.set_quiet`/`repl.py`'s
   `/quiet`/`/loud` branches need the same removal — this is a real behaviour
   change, not an oversight, so it must be intentional in the port too.
5. **`--no-tui` CLI flag** in `boukensha_loader.rb`: `ARGV.delete("--no-tui")`
   before building `repl_opts`, sets `tui: !no_tui`.
6. **`boukensha.gemspec` / `Gemfile`** — new dependency `charm`. Python
   equivalent: `textual` in `pyproject.toml` (see decision above).
7. **`version.rb`**: `0.10.0` → `0.11.0`.
8. **`examples/example.rb`** — unchanged from step 10 (still the MUD demo; it
   doesn't exercise the TUI, matching the Ruby README's own note that the TUI
   is interactive and run via the global executable, not the example script).
9. **`Logger#subscribe`** — already present in **both** Ruby step 10 and the
   existing `python/10_standard_tool_library/boukensha/logger.py` (verified:
   `logger.py` already has `_subscribers`/`subscribe()`/dispatch-in-`write_log`).
   **No change needed here** — it predates this step in both languages.
10. **`patches/bubbletea/`** (native C extension fix for a Ruby/bubbletea
    keystroke-burst-discard bug) — Ruby/native-toolchain-specific, **does
    not need a Python equivalent**. Textual's input handling is a different
    codebase with no reason to share this bug; flag it in verification as
    something to *watch for*, not something to pre-emptively patch.

## New files

1. **`week1_baseline/python/11_tui/`** — seeded as a copy of
   `python/10_standard_tool_library` (excluding `__pycache__`), the same
   strategy used to build step 10 from step 09.
2. **`boukensha/tui.py`** — the Textual `App` subclass, port of `tui.rb`
   per the architecture mapping above:

   - `class BoukenshaApp(App)` wrapping a `Repl`.
   - `compose()` yields the four zones: a scrollable conversation log
     (`RichLog` or equivalent), a progress `Static`, an `Input`, a status
     `Static`.
   - `on_mount()`: seed the log with `repl._banner()`, register
     `repl.on_output(self._append_output)`, register
     `repl.logger.subscribe(self._on_event)` (dispatched via
     `call_from_thread`), focus the input, start the tick timer.
   - `BINDINGS` for `ctrl+c`/`ctrl+d` (quit), `escape` (interrupt),
     `ctrl+l` (clear — reuses `repl.handle_command("/clear")`), `pageup`/
     `pagedown` (scroll).
   - `on_input_submitted`: mirrors `submit_input` — slash commands go through
     `repl.handle_command`; anything else appends to the log and launches a
     `@work(thread=True)` worker calling `repl.run_turn(input)`, catching
     `Interrupt`-equivalent/`Exception` the same way `launch_turn`'s
     `rescue` clauses do, posting a `turn_complete`/`turn_error` event either
     way.
   - Spinner frames, `fmt_tokens`, progress-line/status-line text formatting:
     direct ports of the Ruby helpers (`SPINNER_FRAMES`, `fmt_tokens`,
     `render_progress`, `render_status`), since none of that logic is
     TUI-framework-specific.
   - Import guard: if `textual` isn't installed and `tui=True` is requested,
     raise a clear `ImportError`-derived message pointing at `pip install textual` / `--no-tui`, rather than an opaque traceback — matches Ruby's
     `defined?(Tui)` guard in `boukensha.rb`'s `if tui && defined?(Tui)`.

## Modified files (mirroring the Ruby `10 → 11` deltas)

3. **`boukensha/repl.py`** — the composability refactor from delta #3:

   - `on_output(callback)` — store it; when set, an internal `_output(str)`
     helper calls it instead of `print`.
   - `handle_command(input) -> Literal["quit", "command", None]` — extracted
     from the inline `if`/`elif` chain in `start()`.
   - `run_turn` — rename `_run_turn` → `run_turn` (public), route its prints
     through `_output`.
   - Expose `logger`, `context`, `model`, `version` as read-only properties.
   - Remove the `/quiet`/`/loud` branches from `handle_command` and the
     `HELP` text (delta #4) — `boukensha.set_quiet` stays as a module
     function (still used elsewhere, e.g. `Boukensha.debug?`-equivalent
     logging), just no longer reachable from the REPL.
   - `start()` keeps the `input()`/`EOFError` loop for the no-TUI path,
     rewritten in terms of `handle_command`/`run_turn` so both front-ends
     share one implementation, matching Ruby's `Repl#start` doing the same.
4. **`boukensha/__init__.py`** — `run()`/`repl()` gain a `tui: bool = True`
   kwarg (delta #2); `repl()` does the `if tui: from boukensha.tui import BoukenshaApp; BoukenshaApp(repl).run() else: repl.start()` dispatch, with
   the import-guard behaviour from the `tui.py` note above.
5. **`boukensha/version.py`** — `VERSION = "0.11.0"` (delta #7).
6. **`boukensha_loader.py`** — add `--no-tui` handling to `sys.argv`
   (Python's argv equivalent of `ARGV.delete("--no-tui")`), setting
   `repl_kwargs["tui"] = False` when present (delta #5).
7. **`pyproject.toml`** — `version = "0.11.0"`; add `"textual>=0.60"` (exact
   floor TBD at implementation time) to `[project.dependencies]`; update
   `description` to mention the TUI.
8. **`README.md`** — rewrite as the Step 11 port doc, following the existing
   convention: pointer to the Ruby README for the feature narrative and
   keyboard-shortcut table (unchanged), Python specifics only — which library
   stands in for `charm` and why (link back to the decision above), the
   `--no-tui` flag, and that `examples/example.py` is unchanged (still the
   step-10 MUD demo, doesn't exercise the TUI, matching Ruby's own note).
9. **Everything else** — copied unchanged from step 10: `boukensha/agent.py`,
   `client.py`, `context.py`, `errors.py`, `logger.py` (already has
   `subscribe`, delta #9), `message.py`, `prompt_builder.py`, `registry.py`,
   `tool.py`, `run_dsl.py`, `config.py`, `backends/`, `tools/` (`file_system.py`,
   `shell.py`, `mud.py`, `mcp/`, `tools/mcp.py`, `tools/mud_mcp.py`), `tasks/`,
   `prompts/system.md`, `bin/boukensha`, `mud_manager` (sibling package,
   untouched).

## bin scripts

10. **`bin/11_tui_python`** — same shared-venv bootstrap pattern as
    `10_standard_tool_library_python`, adding `textual` to the `pip install`
    line:

    ```sh
    .venv/bin/pip install -q "python-dotenv>=1.0" "PyYAML>=6.0" "textual>=0.60"
    exec .venv/bin/python 11_tui/bin/boukensha
    ```
11. **`bin/11_tui_ruby`** — same pattern as `10_standard_tool_library_ruby`,
    updated for the now-dependency-free `mud_manager_mcp` (per
    `docs/plans/mud_manager/single_binary.md`, already implemented — the
    vendoring means no separate `mcp_server` gem install step is needed):

    ```sh
    if ! gem list -i mud_manager_mcp -v 0.1.0 >/dev/null 2>&1; then
      gem install --local "$BASE/mud_manager_mcp/mud_manager_mcp-0.1.0.gem"
    fi
    bundle install --quiet
    exec bundle exec ruby bin/boukensha
    ```

    `bundle install` also resolves `charm` (and its native `bubbletea`/
    `lipgloss`/`bubbles`/`bubblezone`/`ntcharts`/`gum`/`glamour`/`harmonica`
    dependency tree) from rubygems.org — no local vendoring needed there,
    unlike `mud_manager_mcp`.

Both scripts `chmod +x`.

## Decisions needed before starting

1. **`esc`-to-interrupt semantics** — does `agent.py`/`client.py` already
   expose a cooperative-cancellation checkpoint (something a worker thread
   could set a flag for, and the blocking HTTP/agent loop checks), or does
   this need new plumbing? If neither, is a documented "interrupt requests
   cancellation but can't abort an in-flight API call" limitation acceptable
   for this step, matching what's realistically achievable without inventing
   new cross-thread cancellation machinery Ruby's `Thread#raise` doesn't need
   an equivalent problem for?
2. **Minimum Textual version** — pin a floor once implementation starts and
   the actual APIs used (worker decorator, specific widgets) are confirmed
   against a real `pip install textual` in this environment.

## Not in scope

- Re-deriving `patches/bubbletea/`'s native-extension fix for whatever
  library is chosen — that bug is specific to the Ruby `bubbletea` gem's C
  extension; Python's TUI stack shares no code with it. If the chosen library
  exhibits its own multi-byte-input-loss bug, that would be a separate,
  newly-discovered issue, not a known port item.
- Windows terminal support beyond whatever the chosen library provides by
  default (Ruby's `charm`/`bubbletea` story here isn't itself
  Windows-verified in this repo either).
- Changing anything in `mud_manager_mcp`, `Boukensha::MCP`, or the standard
  tool library — step 11 is purely additive on top of the already-ported
  step 10 (Python) / already-updated `11_tui` (Ruby, MCP already merged in a
  prior pass per `docs/plans/mud_manager/generic_mcp_server.md`).
- Steps 12+ — this plan covers only `11_tui`. A follow-up plan would handle
  `12_context` the same way once this lands, seeding from `python/11_tui`
  the way Ruby's `12_context` was built from `11_tui`.

## Verification — results

1. **Byte-compile**: `py_compile` across every file in `python/11_tui`,
   including `boukensha_loader.py` — clean. ✅
2. **Import, with and without `textual` installed** — checked in two separate
   venvs (one with `textual==8.2.8`, one without). `boukensha.repl(tui=False)`
   works in both. Without `textual`, calling `boukensha.repl(tui=True, ...)`
   raises a clean `ImportError: boukensha: tui=True requires the 'textual'
   package (pip install textual), or pass tui=False / --no-tui...` — not a raw
   `ModuleNotFoundError` traceback — confirmed by driving the real public
   `repl()` entry point (not just `import boukensha.tui` directly), so the
   guard's actual placement in `__init__.py` is what's verified. ✅
3. **`handle_command`/`run_turn`/`on_output` unit checks** against a throwaway
   `Repl`: `on_output` receives the banner, `/help`, `/clear`, and `/exit`
   text instead of it reaching stdout; `handle_command("/clear")` empties
   `context.messages` and returns `"command"`; `/exit` and `/quit` both return
   `"quit"`; **`/quiet` and `/loud` return `None`** (unrecognized — falls
   through to "run as a turn", matching delta #4's removal); `boukensha.
   set_quiet`/`quiet()` confirmed absent from the module entirely. `banner()`
   confirmed public (not `_banner()`) — checked against Ruby's own
   `attr_reader`/`private` placement (`banner` is declared before `private` in
   `repl.rb`) rather than assumed. ✅
4. **TUI smoke test**, headless via Textual's own `run_test()`/`Pilot` API
   (not a simulated terminal) against a real `Repl`+`Agent`+real `Anthropic`
   backend's response-parsing logic, with only the network call faked: banner
   renders into the log on mount; typing and submitting text drives a real
   `Repl.run_turn` → `Agent.run` → `Client.call` round trip through the
   background worker; the input clears after submit; session token counters
   update from real `Logger` events relayed through `call_from_thread`;
   `PageUp`/`PageDown` don't raise; `Ctrl+L` clears conversation history (both
   `context.messages` and the TUI's own turn counter); a slash command typed
   into the input box (`/help`) is handled without crashing; `Esc` during an
   active (artificially slowed) turn immediately flips the UI back to idle and
   bumps the run id, and the background thread's eventual late callback is
   confirmed **dropped** rather than reactivating the UI; `Ctrl+C` quits
   cleanly. **This is where the `call_from_thread`-on-the-UI-thread bug
   (documented in "Outcome" above) was actually caught** — it did not surface
   during writing or review. ✅
5. **`--no-tui` flag**, through the *real* launcher scripts (not a hand-built
   Python snippet): `bin/11_tui_python --no-tui` and `bin/11_tui_ruby
   --no-tui`, both piped `/exit`, both configured against the live MUD via
   `~/.boukensha` — banners match field-for-field (`v0.11.0`, `mammouth
   (claude-haiku-4-5)  ✓ API key set`, `localhost:4000  (Reachable)`), no
   `/quiet`/`/loud` in either. **This is where the missing `"$@"`
   argument-forwarding bug in both launcher scripts was caught** — without
   it, `--no-tui` never reached the loader and the real full-screen TUI
   launched instead, consuming the piped stdin as raw terminal input rather
   than REPL commands. ✅ (fixed, both scripts re-verified after the fix)
6. **Live agent turn through the TUI against a real backend** (mammouth /
   `claude-haiku-4-5`, the same backend used throughout this repo's live
   verifications): a real network round trip completed in ~2.1s, the model's
   actual reply text ("Hello, test here.") rendered into the conversation log,
   and the JSONL session log recorded real normalized `input_tokens`/
   `output_tokens` (27/8) — confirming the pipeline reaches the LLM, not just
   that the UI renders. Separately confirmed the real public `boukensha.
   repl(tui=True, ...)` entry point (as opposed to a hand-constructed
   `BoukenshaApp`) boots `Textual`'s app loop headlessly without error. ✅
7. **Real full-screen TUI, both languages, through the real launchers with no
   piped/faked input** — `bin/11_tui_ruby` (no flag) and `bin/11_tui_python`
   (no flag), each killed by an outer timeout (expected — a full-screen app
   waiting on real keys has no natural EOF-driven exit). Both rendered a live
   status bar with matching fields: `boukensha v0.11.0 · claude-haiku-4-5 ·
   ctx 0 · **38 tools** · <clock>` — 38 = 31 MUD-over-MCP + 6 FileSystem + 1
   Shell, identical in both languages. Ruby's run additionally confirmed the
   full native `charm`/`bubbletea`/`lipgloss`/`bubbles` dependency chain
   resolves and boots cleanly via `bundle install`, restoring the terminal
   screen correctly on exit. ✅
8. **Side-by-side MUD-over-MCP**, Ruby vs. Python, against the live server at
   `localhost:4000`: both register exactly **31 tools** via `Tools::MudMcp`/
   `MudMcp.register`, both resolve `look` to the same live room
   ("The Dirty Hallway" — same server, same session state at the time). ✅
