"""Port of ``lib/boukensha/agent.rb``.

The agent loop: repeatedly call the model, dispatch any tool calls it makes,
feed the results back, and stop when the model stops asking for tools (or the
iteration/token limits are reached). Every phase of the turn is recorded through
a :class:`boukensha.logger.Logger` instead of being printed to the terminal.
"""

from __future__ import annotations

from typing import Any

from boukensha.client import Client
from boukensha.context import Context
from boukensha.errors import ApiError
from boukensha.logger import Logger
from boukensha.prompt_builder import PromptBuilder
from boukensha.registry import Registry


class Agent:
    # Default iteration ceiling, used when the caller passes no explicit
    # max_iterations. The enforced value normally comes from
    # Config#agent_max_iterations (sourced at the run/repl path). 0 disables
    # the ceiling.
    MAX_ITERATIONS = 25

    # The wind-down call is deliberately short and cheap.
    WRAP_UP_OUTPUT_TOKENS = 400
    WRAP_UP_DIRECTIVE = (
        "You have reached your action limit for this turn. Do not call any more tools.\n"
        "Briefly summarize what you accomplished, what is still unfinished, and the\n"
        "single next action you would take."
    )

    def __init__(
        self,
        *,
        context: Context,
        registry: Registry,
        builder: PromptBuilder,
        client: Client,
        logger: Logger | None = None,
        max_iterations: int | None = None,
        max_turn_tokens: int | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        self._context = context
        self._registry = registry
        self._builder = builder
        self._client = client
        self._logger = logger if logger is not None else Logger()
        self._max_iterations = int(max_iterations) if max_iterations is not None else self.MAX_ITERATIONS
        self._max_turn_tokens = int(max_turn_tokens or 0)  # 0 = disabled
        self._max_output_tokens = max_output_tokens
        self._iteration = 0

    def run(self) -> str:
        self._context.reset_turn_tokens()
        self._compact_if_needed()

        while True:
            # Two independent ceilings; stop at whichever trips first. Limits
            # are *trigger thresholds*, not hard caps: when one is reached we
            # stop starting new work iterations and make exactly one terminal
            # wind-down call (counted in tokens, but not as another iteration).
            if self._iteration_limit_reached():
                self._logger.limit_reached(
                    kind="max_iterations", n=self._iteration, max=self._max_iterations
                )
                return self._wrap_up("max_iterations")

            if self._token_limit_reached():
                self._logger.limit_reached(
                    kind="max_tokens", n=self._context.turn_tokens, max=self._max_turn_tokens
                )
                return self._wrap_up("max_tokens")

            self._iteration += 1
            self._logger.iteration(n=self._iteration, max=self._max_iterations)
            self._logger.prompt(
                messages=self._context.messages,
                tools=self._context.tools,
                context_window=self._context.context_window,
            )

            response = self._client.call(**self._call_opts())
            self._logger.raw(data=response)
            parsed = self._builder.parse_response(response)
            self._record_usage(response)
            self._log_reasoning(parsed["content"])

            if parsed["stop_reason"] == "tool_use":
                self._handle_tool_calls(parsed["content"], response)
            else:
                text = self._extract_text(parsed["content"])
                self._logger.response(
                    text=text, usage=response.get("usage"), stop_reason=parsed["stop_reason"]
                )
                self._logger.turn_end(
                    reason="completed", iterations=self._iteration, tokens=self._context.turn_tokens
                )
                self._context.add_message("assistant", text)
                return text

    # ---------- internals ----------------------------------------------------

    def _iteration_limit_reached(self) -> bool:
        return self._max_iterations > 0 and self._iteration >= self._max_iterations

    def _token_limit_reached(self) -> bool:
        return self._max_turn_tokens > 0 and self._context.turn_tokens >= self._max_turn_tokens

    # Per-call options shared by every model round-trip of the turn.
    def _call_opts(self) -> dict[str, Any]:
        return {"max_output_tokens": self._max_output_tokens} if self._max_output_tokens else {}

    # Add this call's input+output to the cumulative turn total (the spend
    # budget) and refresh the known context size from input_tokens (compaction
    # pressure). The trigger is evaluated on pre-wrap-up spend; the reported
    # total includes the wind-down call too.
    def _record_usage(self, response: dict[str, Any]) -> None:
        usage = response.get("usage") or {}
        self._context.add_turn_tokens(usage.get("input_tokens"), usage.get("output_tokens"))
        self._context.update_tokens(usage.get("input_tokens") or 0)

    def _compact_if_needed(self) -> None:
        if not self._context.needs_compaction():
            return

        before = self._context.current_tokens
        dropped = self._context.compact_messages()
        self._logger.compaction(
            before=before, dropped=dropped, context_window=self._context.context_window
        )

    # Emit one `reasoning` event per reasoning block so the viewer can show the
    # model's thinking as a first-class step. Empty, non-redacted blocks are
    # skipped to avoid noise (a redacted/omitted block still renders, since it
    # tells the viewer "the model thought here").
    def _log_reasoning(self, content: list[dict[str, Any]]) -> None:
        for block in content:
            if block.get("type") != "reasoning":
                continue

            redacted = block.get("redacted") is True
            text = str(block.get("text") or "")
            if not text.strip() and not redacted:
                continue

            self._logger.reasoning(text=text, redacted=redacted)

    # One final, tools-disabled model call so the agent ends the turn in
    # character rather than aborting. Runs *outside* the counted loop: it never
    # re-checks the limits (so it cannot re-trigger) and does not increment
    # @iteration, though its tokens still count toward the reported turn total.
    # Falls back to a deterministic message if the call fails.
    def _wrap_up(self, reason: str) -> str:
        self._context.add_message("user", self.WRAP_UP_DIRECTIVE)
        try:
            response = self._client.call(tools=[], max_output_tokens=self.WRAP_UP_OUTPUT_TOKENS)
            parsed_wrap = self._builder.parse_response(response)
            text = self._extract_text(parsed_wrap["content"])
            if not text.strip():
                text = self._fallback_message(reason)
            self._record_usage(response)
            self._logger.response(
                text=text, usage=response.get("usage"), stop_reason=parsed_wrap["stop_reason"]
            )
            self._logger.turn_end(
                reason=reason, iterations=self._iteration, tokens=self._context.turn_tokens
            )
            self._context.add_message("assistant", text)
            return text
        except ApiError:
            msg = self._fallback_message(reason)
            self._logger.turn_end(
                reason=reason, iterations=self._iteration, tokens=self._context.turn_tokens
            )
            self._context.add_message("assistant", msg)
            return msg

    def _fallback_message(self, reason: str) -> str:
        return (
            f"I reached my {self._max_iterations}-action limit for this turn before "
            f"finishing ({reason}). Ask me to continue and I'll pick up from here."
        )

    @staticmethod
    def _extract_text(content: list[dict[str, Any]]) -> str:
        return "\n".join(b["text"] for b in content if b["type"] == "text")

    def _handle_tool_calls(self, content: list[dict[str, Any]], response: dict[str, Any]) -> None:
        tool_calls = [b for b in content if b["type"] == "tool_use"]

        # Log any preamble text that accompanied the tool call (carries no
        # usage — the placeholder below owns the turn's usage chip), then the
        # placeholder.
        preamble = self._extract_text(content)
        if preamble.strip():
            self._logger.plan(text=preamble)

        n = len(tool_calls)
        placeholder = f"(tool use — {n} call{'s' if n != 1 else ''})"
        self._logger.response(text=placeholder, usage=response.get("usage"), stop_reason="tool_use")

        self._context.add_message("assistant", content)

        for block in tool_calls:
            name = block["name"]
            args = block["input"]
            use_id = block["id"]

            self._logger.tool_call(name=name, args=args)
            try:
                result: Any = self._registry.dispatch(name, args)
                self._logger.tool_result(name=name, result=result, ok=True)
            except Exception as e:  # noqa: BLE001 — mirror Ruby's rescue StandardError
                result = f"ERROR: {type(e).__name__}: {e}"
                self._logger.tool_result(name=name, result=result, ok=False, error=str(e))

            self._context.add_message("tool_result", str(result), tool_use_id=use_id)
