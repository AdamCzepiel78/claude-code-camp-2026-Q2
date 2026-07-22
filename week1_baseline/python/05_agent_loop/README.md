# 05 · The Agent Loop (Python port)

Python 3 port of [`ruby/05_agent_loop`](../../ruby/05_agent_loop/README.md). Same design — see
the Ruby README for the full considerations. This document covers the Python-specific
implementation and how it differs from the Ruby source.

This is the step where the agent actually does work. Everything before it — the structs, the
registry, the prompt builder, the client — was setup. `Agent` drives the loop: call the model,
dispatch any tool calls it makes, feed the results back, and repeat until the model stops asking
for tools (or the iteration limit is reached).

```
send messages to API
        ↓
stop_reason == "tool_use"?
    yes → extract tool calls
        → dispatch each tool via Registry
        → inject results as tool_result messages
        → go back to top
    no  → return final text response
```

## New file (vs. step 4)

| File | Purpose |
|---|---|
| `boukensha/agent.py` | `Agent` — runs the loop, dispatches tools, and knows when to stop |

`boukensha/errors.py` gains `LoopError` alongside the existing errors.

## `boukensha.agent.Agent`

| Method | Description |
|---|---|
| `Agent(*, context, registry, builder, client, task_settings=None, max_iterations=None, max_output_tokens=None)` | Wires the loop's collaborators; resolves limits from `task_settings` (or explicit overrides) |
| `run()` | Starts the loop and returns the final text response when the agent is done |

The iteration and output-token limits come from `tasks.player.max_iterations` /
`max_output_tokens` in `settings.yaml` (resolved via `Player.max_iterations` /
`max_output_tokens`), falling back to `Agent.MAX_ITERATIONS` (25) and the model default.
Reaching the limit is a *trigger*, not a hard cap: the loop makes exactly one final,
tools-disabled "wind-down" call so the agent ends its turn in character rather than raising.
If that call fails, `Agent` returns a deterministic fallback message.

## Every backend speaks the same normalized shape

Six providers means six different response formats. Rather than teach the loop about each, every
backend implements `parse_response`, converting its raw response into one common shape that
`PromptBuilder.parse_response` delegates to:

```python
{
    "stop_reason": "tool_use" | "end_turn",
    "content": [
        {"type": "text", "text": "..."},
        {"type": "tool_use", "id": "...", "name": "...", "input": {...}},
    ],
}
```

`Agent` only ever sees this shape — it never inspects a raw provider response, which keeps
`run()` down to a single `if parsed["stop_reason"] == "tool_use"` branch.

The conversion also runs in reverse. When the conversation history is replayed on the next
request, `OpenAI`, `Mammouth`, `Ollama`, `OllamaCloud`, and `Gemini` each rebuild a
provider-specific assistant message from the normalized `content` blocks via a private
`_assistant_message` / `_assistant_parts` method — the inverse of `parse_response`. Anthropic's
`content` array doubles as both the normalized shape and the wire format, so it needs no extra
conversion.

**Tool call IDs aren't universal.** Anthropic, OpenAI, and Mammouth assign every tool call a
unique `id`, echoed back in the `tool_result`. Ollama, Ollama Cloud, and Gemini don't assign
call ids at all — those backends reuse the tool's `name` as its `id` and match the `tool_result`
back to the call by name.

## What's different from the Ruby source

- **`Message.content` is widened** from `str` to `str | list[dict]`. The agent stores an
  assistant turn as the raw list of content blocks the model returned; `Context.add_message`
  accepts the same widened type.
- The `Client.call` / `PromptBuilder.to_api_payload` / backend `to_payload` methods all gain a
  `tools=None` keyword. The wind-down call passes `tools=[]` to disable tool use for the final
  turn; every other call leaves it `None`, so the backend uses its own `to_tools(context.tools)`.
- `OpenAI` and `Mammouth` gain a `json` import to (de)serialize tool-call `arguments`, which the
  OpenAI-compatible wire format carries as a JSON string.
- The Ruby `config.rb` change in this step was cosmetic (endless-method syntax); the Python
  `config.py` is unchanged. The Ruby source also drops its `mammouth` backend at this step —
  the Python port keeps it, giving it the same `parse_response` / `_assistant_message` treatment
  as the other OpenAI-compatible backends.

## Running it

```
bin/05_agent_loop_python   # from week1_baseline/
```

Sends real HTTP requests to whatever `provider`/`model` is configured in
`.boukensha/settings.yaml` and prints the per-iteration trace followed by the final response.
Run `bin/05_agent_loop_ruby` for the byte-comparable Ruby output.
