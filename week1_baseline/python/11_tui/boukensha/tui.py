"""Port of ``lib/boukensha/tui.rb``.

``charm`` (Ruby bindings over the Go ``bubbletea``/``lipgloss``/``bubbles``
libraries) has no Python equivalent, so this is a port to a different toolkit
— `Textual <https://textual.textualize.io/>`_ — rather than a line-for-line
translation. One library covers everything bubbletea (event loop) +
lipgloss (styling) + bubbles (widgets) covered together.

``BoukenshaApp`` wraps a :class:`~boukensha.repl.Repl` instance and replaces
its raw ``print``/``input`` I/O with a structured four-zone display:

    ┌──────────────────────────────────────────────┐
    │  conversation log (scrollable)                │
    ├──────────────────────────────────────────────┤
    │  ⟳ live progress line (hidden when idle)      │
    ├──────────────────────────────────────────────┤
    │  boukensha> input box                         │
    ├──────────────────────────────────────────────┤
    │  status line (always-on)                      │
    └──────────────────────────────────────────────┘

Ruby's version manually tracks terminal width/height and re-renders a joined
string on every message (bubbletea's lower-level model). Textual's CSS layout
resizes the widgets automatically, so there is no ``on_resize`` handler here —
one of the genuine simplifications the higher-level toolkit buys.

The Repl continues to own session logic (turn counting, /commands, Agent
dispatch). This module registers output/event callbacks on the Repl and drives
the turn in a background thread via Textual's ``@work(thread=True)`` worker —
the natural replacement for Ruby's ``Thread.new { @repl.run_turn(input) }`` +
manual ``Queue`` draining, since Textual's ``call_from_thread`` already
provides a thread-safe hop back onto the UI event loop.

## Interrupt (Esc) semantics — a deliberate, documented limitation

Ruby's ``esc`` handler calls ``@turn_thread.raise(Interrupt)``, which *can*
abort a blocking ``Net::HTTP`` call mid-flight because MRI delivers an
async-raised exception at the next I/O interrupt point. Python threads have no
safe equivalent — the closest mechanism (``ctypes``-based async exception
injection into another thread) only takes effect at the next Python bytecode
boundary, which for a blocking ``socket.recv()`` inside ``http.client`` is no
earlier than when the call already returns, so it buys nothing over a plain
flag while adding real risk (raising mid-``finally``, leaking sockets).

So here, ``Esc`` marks the turn's ``run_id`` stale and returns control to the
UI immediately — the background thread's blocking HTTP call keeps running to
completion (typically a few seconds), and its result is silently discarded
when it calls back, because the callback checks the run id and finds it no
longer current. From the user's perspective the UI unblocks right away, which
is the behaviour that actually matters; the in-flight request is not aborted
early, only its result is ignored.
"""

from __future__ import annotations

import datetime
import time
from typing import Any

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static
from textual.worker import NoActiveWorker, get_current_worker

from boukensha.agent import Agent
from boukensha.repl import PROMPT, Repl

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
TICK_SECONDS = 0.06  # 60ms, matching Ruby's TickMsg cadence


class BoukenshaApp(App):
    """Textual front-end for :class:`~boukensha.repl.Repl`."""

    CSS = """
    Screen {
        layout: vertical;
    }
    #log {
        height: 1fr;
        border: none;
    }
    #progress {
        height: 1;
        padding: 0 1;
    }
    #input-row {
        height: 1;
    }
    #prompt-label {
        width: auto;
        color: green;
        text-style: bold;
    }
    #input {
        border: none;
        background: $surface;
    }
    #status {
        height: 1;
        background: #808080;
        color: white;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+d", "quit", "Quit", priority=True),
        Binding("escape", "interrupt", "Interrupt"),
        Binding("ctrl+l", "clear", "Clear"),
        Binding("pageup", "scroll_up", "Scroll up"),
        Binding("pagedown", "scroll_down", "Scroll down"),
    ]

    def __init__(self, repl: Repl) -> None:
        super().__init__()
        self._repl = repl
        self._turn_count = 0
        self._session_input_tokens = 0
        self._session_output_tokens = 0
        self._active_run_id = 0
        self._turn_start = 0.0

        self._live: dict[str, Any] = self._idle_live_state()

    # ---------- Textual lifecycle ---------------------------------------------

    def compose(self) -> ComposeResult:
        yield RichLog(id="log", auto_scroll=True, markup=False)
        yield Static("", id="progress")
        with Horizontal(id="input-row"):
            yield Static(PROMPT, id="prompt-label")
            yield Input(placeholder="Type a message…", id="input")
        yield Static("", id="status")

    def on_mount(self) -> None:
        log = self.query_one("#log", RichLog)
        log.write(self._repl.banner())

        self._repl.on_output(self._on_repl_output)
        self._repl.logger.subscribe(self._on_logger_event)

        self.query_one("#input", Input).focus()
        self._render_progress()
        self._render_status()
        self.set_interval(TICK_SECONDS, self._on_tick)

    # ---------- output / event plumbing ---------------------------------------
    #
    # Both callbacks below fire from Repl.handle_command/run_turn — sometimes
    # from the worker thread (during a live turn, run_turn runs inside
    # @work(thread=True)), sometimes directly on the UI thread (a slash
    # command dispatched from a key binding, e.g. Ctrl+L -> action_clear ->
    # handle_command("/clear")). Textual's call_from_thread refuses to run
    # when already on the UI thread (raises RuntimeError), so the dispatch
    # must check which thread it's on — get_current_worker()/NoActiveWorker is
    # the sanctioned way to ask. This is the same thread-safety boundary Ruby
    # crosses with its Queue + tick-drain, just resolved directly here instead
    # of hand-rolled.

    def _in_worker_thread(self) -> bool:
        try:
            get_current_worker()
            return True
        except NoActiveWorker:
            return False

    def _on_repl_output(self, text: str) -> None:
        if self._in_worker_thread():
            self.call_from_thread(self._append_log, text)
        else:
            self._append_log(text)

    def _on_logger_event(self, event: dict[str, Any]) -> None:
        if self._in_worker_thread():
            self.call_from_thread(self._handle_event, self._active_run_id, event)
        else:
            self._handle_event(self._active_run_id, event)

    def _append_log(self, text: str) -> None:
        self.query_one("#log", RichLog).write(str(text))

    # ---------- input handling -------------------------------------------------

    def on_input_submitted(self, message: Input.Submitted) -> None:
        text = message.value.strip()
        message.input.value = ""
        if not text:
            return

        if text.startswith("/"):
            result = self._repl.handle_command(text)
            if result == "quit":
                self.exit()
            elif text == "/clear":
                self._turn_count = 0
            return

        self._append_log(f"> {text}")
        self._launch_turn(text)

    # ---------- actions (bound keys) -------------------------------------------

    def action_quit(self) -> None:
        self.exit()

    def action_interrupt(self) -> None:
        if not self._live["active"]:
            return
        # Bump the run id so the background thread's eventual callback (it is
        # still running — see the module docstring) is recognised as stale and
        # dropped rather than acted on.
        self._active_run_id += 1
        self._live = self._idle_live_state()
        self._append_log("[interrupted]")
        self._render_progress()

    def action_clear(self) -> None:
        result = self._repl.handle_command("/clear")
        if result == "command":
            self._turn_count = 0

    def action_scroll_up(self) -> None:
        self.query_one("#log", RichLog).scroll_page_up()

    def action_scroll_down(self) -> None:
        self.query_one("#log", RichLog).scroll_page_down()

    # ---------- turn lifecycle ---------------------------------------------------

    def _launch_turn(self, text: str) -> None:
        self._active_run_id += 1
        run_id = self._active_run_id
        self._live = {
            "active": True,
            "spinner_idx": 0,
            "elapsed": 0.0,
            "current_action": "Thinking…",
            "iteration": 0,
            "tool_call_count": 0,
            "turn_input_tokens": 0,
            "turn_output_tokens": 0,
        }
        self._turn_start = self._now()
        self._render_progress()
        self._run_turn_worker(text, run_id)

    @work(thread=True)
    def _run_turn_worker(self, text: str, run_id: int) -> None:
        try:
            self._repl.run_turn(text)
        except Exception as e:  # noqa: BLE001 — mirror Ruby's broad rescue in the turn thread
            self.call_from_thread(self._handle_event, run_id, {"phase": "turn_error", "error": str(e)})
            return
        self.call_from_thread(self._handle_event, run_id, {"phase": "turn_complete"})

    def _handle_event(self, run_id: int, event: dict[str, Any]) -> None:
        if run_id != self._active_run_id:
            return  # stale — a newer turn started, or this one was interrupted

        phase = str(event.get("phase", ""))

        if phase == "iteration":
            self._live["iteration"] = int(event.get("n", 0))
            self._live["current_action"] = "Thinking…"

        elif phase == "tool_call":
            self._live["current_action"] = f"Calling tool: {event.get('name')}"
            self._live["tool_call_count"] += 1

        elif phase == "tool_result":
            self._live["current_action"] = "Awaiting result…"

        elif phase == "response":
            usage = event.get("usage")
            if usage:
                itu = int(usage.get("input_tokens", 0) or 0)
                otu = int(usage.get("output_tokens", 0) or 0)
                self._live["turn_input_tokens"] += itu
                self._live["turn_output_tokens"] += otu
                self._session_input_tokens += itu
                self._session_output_tokens += otu

        elif phase == "turn_complete":
            self._live["active"] = False
            self._turn_count += 1

        elif phase == "turn_error":
            self._live["active"] = False
            self._append_log(f"[error] {event.get('error')}")

        self._render_progress()
        self._render_status()

    # ---------- ticking ----------------------------------------------------------

    def _on_tick(self) -> None:
        if self._live["active"]:
            self._live["spinner_idx"] = (self._live["spinner_idx"] + 1) % len(SPINNER_FRAMES)
            self._live["elapsed"] = self._now() - self._turn_start
        self._render_progress()
        self._render_status()

    # ---------- rendering ----------------------------------------------------------

    def _render_progress(self) -> None:
        widget = self.query_one("#progress", Static)
        if self._live["active"]:
            frame = SPINNER_FRAMES[self._live["spinner_idx"]]
            action = self._live["current_action"]
            iteration = self._live["iteration"]
            max_iter = Agent.MAX_ITERATIONS
            secs = int(self._live["elapsed"])
            itok = self._fmt_tokens(self._live["turn_input_tokens"])
            otok = self._fmt_tokens(self._live["turn_output_tokens"])
            calls = self._live["tool_call_count"]
            widget.update(
                f"[cyan]{frame} {action}  "
                f"(iter {iteration}/{max_iter} · {secs}s · "
                f"↑ {itok} · ↓ {otok} · {calls} calls)[/cyan]"
            )
        else:
            used = self._fmt_tokens(self._session_input_tokens)
            widget.update(f"[#808080]  [ready]   ctx {used}   {self._turn_count} turns[/#808080]")

    def _render_status(self) -> None:
        widget = self.query_one("#status", Static)
        ver = self._repl.version or "?"
        model = self._repl.model or "(model)"
        used = self._fmt_tokens(self._session_input_tokens)
        tools = self._repl.context.tool_count
        clock = self._now_str()
        bar = f" boukensha v{ver} · {model}  ·  ctx {used}  ·  {tools} tools  ·  {clock} "
        widget.update(bar)

    @staticmethod
    def _fmt_tokens(n: int) -> str:
        n = int(n)
        return f"{n / 1000.0:.1f}k" if n >= 1000 else str(n)

    @staticmethod
    def _idle_live_state() -> dict[str, Any]:
        return {
            "active": False,
            "spinner_idx": 0,
            "elapsed": 0.0,
            "current_action": "idle",
            "iteration": 0,
            "tool_call_count": 0,
            "turn_input_tokens": 0,
            "turn_output_tokens": 0,
        }

    @staticmethod
    def _now() -> float:
        return time.monotonic()

    @staticmethod
    def _now_str() -> str:
        return datetime.datetime.now().strftime("%H:%M:%S")
