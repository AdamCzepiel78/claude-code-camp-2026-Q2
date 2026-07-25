# 12 · Context Management (Python port)

Python 3 port of [`ruby/12_context`](../../ruby/12_context/README.md) — with
one important caveat: **the Ruby README undersells its own step.** It documents
only context-window tracking, colour-coded usage, auto-compaction, and
`/compact`. A full diff against `ruby/11_tui` shows the step actually ships
four more substantial changes the Ruby README never mentions: reasoning-block
plumbing across every backend, an OpenAI Responses API migration, the removal
of the `Tasks::Base`/`Tasks::Player` class hierarchy, and (in Ruby) the
removal of the `mammouth` backend. This document covers all of it — what's
actually in the source, not just what the original README describes.

Everything from [step 11](../11_tui/README.md) — the Textual TUI, the standard
tool library, `boukensha.mcp`, MUD tools via `mud_manager_mcp` by default,
config-driven `mcp_servers:` — carries forward. This step changes how the
agent tracks its context window, how backends handle reasoning content, and
how configuration works.

## Two deliberate deviations from the Ruby source

1. **`mammouth` stays.** Ruby's `12_context` drops the backend entirely (file
   removed, dispatch case removed). This port keeps it, on request — nothing
   else about this step depends on that choice, and `mammouth` remains a
   fully supported `backend=` value here.
2. **`boukensha.models` is a real fix, not a bug-for-bug port.** Ruby's
   `Models::TABLE` is a second, standalone model → context-window table,
   consulted *before* the backend object exists, and it only lists three
   Claude models — any other model (Gemini, OpenAI, Ollama, and here,
   Mammouth) silently falls back to a conservative 32,000-token default
   instead of its real window. That table can't just be filled in here
   either: Mammouth's own model catalogue reuses names that also exist in
   Anthropic's table (`"claude-haiku-4-5"` is 200,000 tokens direct against
   Anthropic, 1,000,000 tokens through Mammouth's proxy), so a lookup keyed
   on model name alone can't tell them apart. The actual fix: the backend is
   now constructed *before* `Context` (nothing in between needs it built
   later), and `context_window` is read straight from `backend.context_window`
   — always correct, per-backend, no duplication, no ambiguity.
   `boukensha.models.context_window(provider, model)` still exists as a
   secondary, best-effort lookup for callers without a live backend instance,
   disambiguated by provider name (a real API improvement over Ruby's
   single-argument version).

## What's new

### The `Tasks::Base`/`Tasks::Player` indirection is gone

Every prior step routed provider/model/system-prompt/limit lookups through a
`task_settings` dict and `boukensha.tasks.player.Player` class methods.
That whole layer is deleted. `Config` now exposes it directly:

| Was | Now |
|---|---|
| `Player.provider(task_settings)` | `Config.provider_type` → `settings["tasks"]["player"]["provider"]` or `"anthropic"` |
| `Player.model(task_settings)` | `Config.model` → `...["model"]` or `"claude-haiku-4-5"` |
| `Player.system_prompt(task_settings, ...)` | `Config.system_prompt` (computed once at load time) |
| `Base.max_iterations(task_settings)` | `Config.agent_max_iterations` → `settings["agent"]["max_iterations"]` or `25` |
| `Base.max_output_tokens(task_settings)` | `Config.agent_max_output_tokens` → `...["max_output_tokens"]` or `1024` |
| *(new)* | `Config.agent_max_turn_tokens` → `...["max_turn_tokens"]` or `60000` |
| *(new)* | `Config.agent_compaction_threshold` → `...["compaction_threshold"]` or `0.85` |

**The system prompt source changed too.** Every prior step fell back to a
step-bundled `prompts/system.md` when the config directory had none. That
fallback is gone — `python/12_context` ships **no `prompts/` directory at
all**. `Config.system_prompt` reads only from the *config* directory
(`~/.boukensha/prompts/system.md`, or `~/.boukensha/prompts/player/system.md`
when `tasks.player.prompt_override.system: true`). A config directory with
neither file, and no explicit `system=` argument, means the agent runs with
**no system prompt** — a real behavioural change from every prior step.

`Context` no longer takes a `task=` argument at all.

### Context window tracking, colour coding, auto-compaction

`Context` now tracks two distinct numbers:

| Attribute | What it measures |
|---|---|
| `context_window` | The model's input-token ceiling (from `backend.context_window`) |
| `current_tokens` | Tokens actually used in the most recent API call |

The Agent updates `current_tokens` after every response, so the TUI's display
always reflects what the *next* call will send. The progress/status lines
colour-code it: grey under 70%, yellow at 70–84%, red (with a `⚠`) at 85%+.

At the start of each turn, if `current_tokens / context_window` is at or
above `Config.agent_compaction_threshold` (default 0.85), `Agent` compacts
automatically — drops the oldest ~40% of messages (keeping at least 2) and
resets `current_tokens` to 0. A `Logger.compaction` event is recorded, and
the TUI shows `[context compacted — N messages dropped to free space]`.

Compact manually with `/compact` (REPL or TUI) — same drop logic, on demand:

```
boukensha> /compact
(compacted context — 12 messages dropped)
```

### A second, independent turn-token ceiling

`max_iterations` (a count of agent loop iterations) already existed. This
step adds `max_turn_tokens` (a cumulative input+output token budget for the
turn, default 60,000, 0 = disabled) — whichever ceiling trips first ends the
turn with the same one-call wind-down (`Agent` never lets a turn run forever
just because it's calling few tools but burning a lot of tokens per call).

### Reasoning-block plumbing — passive, not a "thinking on" switch

Every backend's `parse_response` now returns a normalized `"reasoning"`
content-block type (alongside the existing `"text"`/`"tool_use"`) when a
provider includes one — see `boukensha/backends/base.py` for the full
contract. **Checked directly against every backend's request payload: none
of them turn thinking on.** Gemini explicitly sends `thinkingConfig:
{"thinkingBudget": 0}`; Ollama/OllamaCloud send `"think": False`; OpenAI
sends `reasoning={"effort": "none"}` (required by `gpt-5.x` when tools are in
play — see below); Anthropic never requests it. This is defensive plumbing —
handle a reasoning block correctly if one ever appears — not a new visible
chain-of-thought feature this step turns on.

`Agent` logs each reasoning block via a new `Logger.reasoning(text=,
redacted=)` event, and any preamble text accompanying a tool call via a new
`Logger.plan(text=)` event (previously folded into the tool-use placeholder's
response text).

### OpenAI: migrated to the Responses API

`gpt-5.x` rejects `reasoning_effort` + tools on `/v1/chat/completions`
("Please use /v1/responses"), so `backends/openai.py` now targets
`/v1/responses` entirely — not a parameter tweak, a different wire protocol:

- Messages become `input` items; the system prompt moves to a top-level
  `instructions` string instead of a leading system message.
- Tool defs are flat (`{"name":..., "parameters": {...}}`, no `function:`
  wrapper).
- Tool results round-trip via `function_call_output` items keyed by
  `call_id`, not a `{"role": "tool"}` message.
- `parse_response` reads a typed `output[]` array (`"reasoning"`,
  `"message"`, `"function_call"`) instead of `choices[0].message`.

`PromptBuilder.to_messages()` (a convenience method, not used by the normal
request path) calls `backend.to_messages(...)` by a fixed name — since
`OpenAI` no longer has that method at all (renamed to `to_input`), calling
`PromptBuilder.to_messages()` against an `OpenAI`-backed builder now raises
`AttributeError` rather than the `TypeError` it raised before (still only
valid against `Anthropic`/`Gemini`).

### `Logger` — simpler, less per-response metadata

`Logger.response(...)` no longer accepts `task=`/`backend=`, and the
per-response `input_tokens`/`output_tokens`/`cost_usd`/`provider`/`model`
fields it used to compute from them are gone. Every response event now logs
the backend's *raw* usage dict as-is (`response.get("usage")`), with no
cross-provider key normalization and no cost estimate — `session_start`
remains the only place `model`/`provider` are recorded per session. This is a
real reduction in per-response log richness, ported faithfully rather than
preserved as a superset.

Two new event methods: `Logger.compaction(before=, dropped=, context_window=)`
and `Logger.reasoning(text=, redacted=)`, plus `Logger.plan(text=)`.
`Logger.prompt(...)` gained a required `context_window=` parameter.

## Run the demo

```sh
python examples/example.py     # step-10 MUD demo, unchanged

# or via the global executable pointed at this step:
BOUKENSHA_PATH=~/…/python/12_context boukensha           # Textual TUI
BOUKENSHA_PATH=~/…/python/12_context boukensha --no-tui  # plain REPL
```

## Install

```sh
pip install "python-dotenv>=1.0" "PyYAML>=6.0" "textual>=8.0"
```

No new dependencies over step 11.
