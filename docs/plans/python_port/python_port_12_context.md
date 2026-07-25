# Plan: Port `ruby/12_context` → `python/12_context`

Status: **implemented and extensively verified — see "Outcome" below**
Date: 2026-07-25

**Decisions taken by the user:**
1. `mammouth` — **keep it** (deliberate Python-side deviation from Ruby's removal).
2. `models.py`'s table — **fix it** (enrich with every backend's own per-model
   `context_window`, not a bug-for-bug port of Ruby's 3-model table).
3. README scope — full actual feature set (the plan's own recommendation,
   unopposed).

## Scope

Port the Ruby `12_context` step into `week1_baseline/python/12_context`, seeded
from `python/11_tui` (the same strategy used for every prior step), plus
launcher scripts `bin/12_context_python` and `bin/12_context_ruby`.

## Outcome — 2026-07-25

Implemented at `week1_baseline/python/12_context/` (seeded from `python/11_tui`)
plus `bin/12_context_python`/`bin/12_context_ruby`. All three decisions were
applied as recorded at the top of this document.

**The real fix for Decision 2 turned out to be a reorder, not a bigger
table.** `boukensha/models.py` exists (per-provider `context_window(provider,
model)`, disambiguated), but it isn't the primary path: `boukensha/__init__.py`
now constructs the backend *before* `Context` — nothing between them needed
the backend built later, checked directly against the previous order — so
`context_window` comes from `backend.context_window` (always correct,
per-backend). This is what actually solves the ambiguity Decision 2 was about:
Mammouth's `"claude-haiku-4-5"` (1,000,000 tokens) and Anthropic's own
identically-named model (200,000 tokens) can't be told apart by a name-only
table no matter how complete it is. Verified live: both backends resolve
their own correct, different window for the same model name
(`models_backends_test_12.py`).

**A significant, live-confirmed design limitation — inherited from Ruby,
not introduced here — reported rather than silently fixed:**
Context-window tracking and auto-compaction (this step's headline feature)
only actually function for backends whose raw HTTP response nests token
counts under a top-level `"usage"` key with `input_tokens`/`output_tokens`
sub-keys. `Agent._record_usage` (and Ruby's identical `record_usage`) reads
exactly that shape with no per-provider normalization — the `_normalized_usage`
helper that used to bridge this (checking `usage`/`usageMetadata`/
`prompt_eval_count`+`eval_count`) was deleted in this step (Part F). Checked
directly against each backend's actual raw response shape:
- **Works**: Anthropic (native shape matches exactly).
- **Believed to work, not live-verified**: OpenAI's Responses API (its
  `usage` object is documented as `input_tokens`/`output_tokens` — this
  environment's `OPENAI_API_KEY` is a placeholder value (`"lime"`, 4
  characters), not a real key, so this couldn't be confirmed with a live call
  this session).
- **Silently broken in Ruby's actual current source too**: Gemini (its raw
  response carries `usageMetadata`, not `usage` — `gemini.rb` never
  references either key, so nothing repackages it) and Ollama/OllamaCloud
  (token counts are top-level `prompt_eval_count`/`eval_count` fields, no
  `usage` object at all).
- **Silently broken for Mammouth** (kept per Decision 1): confirmed with a
  real network call — raw usage is OpenAI-Chat-Completions-shaped
  (`prompt_tokens`/`completion_tokens`), so `current_tokens` stayed at 0
  across 4 real turns in `live_compaction_test_12.py`, and auto-compaction
  never fired despite a deliberately tiny context window.

Ported exactly as Ruby has it (no per-backend usage normalization added) —
this is a real design question bigger than Decisions 1–3 covered, and
deserves the user's explicit call rather than a unilateral fix, the same way
the step-10 `client.py` header bug was flagged rather than silently patched.
The compaction *mechanism itself* is fully correct and unit/integration
tested (`context_test_12.py`, `agent_test_12.py`) — the gap is specifically
in which backends ever feed it real numbers.

Two more findings, both confirmed and handled as designed (not bugs):
- `PromptBuilder.to_messages()`'s failure mode for OpenAI changed from
  `TypeError` (wrong arity) to `AttributeError` (method renamed to
  `to_input`) — expected, documented in the docstring, matches Ruby's
  `ArgumentError` → `NoMethodError` shift.
- Ruby's TUI textarea-width fix (`@textarea.width = @width -
  Repl::PROMPT.length`) has no Python equivalent to port — Textual's CSS
  layout auto-sizes the `Input` inside its `Horizontal` container, so the
  bug it fixes never existed in this port to begin with.

## Important: the step is much larger than its own README describes

`ruby/12_context/README.md` documents only context-window tracking,
colour-coded usage display, auto-compaction, `/compact`, and a
`Logger#compaction` event. That is real and is part of this step — but a full
diff against `ruby/11_tui` (the actual source of truth, not the README) shows
**four more substantial, undocumented changes** shipped in the same step:

1. **Reasoning-block plumbing — passive, not an "enable thinking" switch.**
   A new normalized `"reasoning"` content-block contract (documented in
   `backends/base.rb`, not the README) that every backend now correctly
   parses/round-trips if a provider returns one, plus `Agent` logging each
   reasoning block via a new `Logger#reasoning` event and a second new
   `Logger#plan` event for preamble text accompanying a tool call. **Checked
   directly against every backend's actual request payload: none of them
   turn thinking ON.** Gemini explicitly sends `thinkingConfig:
   {thinkingBudget: 0}` (or `{thinkingLevel: "LOW"}` for the one model
   that doesn't support a full disable); Ollama/OllamaCloud send `think:
   false`; OpenAI sends `reasoning: {effort: "none"}` (required by
   `gpt-5.x` when tools are in play — the actual reason this step forced
   the Responses API migration below, per Part C); Anthropic's `to_payload`
   never adds a `thinking:` key at all. So this is defensive plumbing —
   correctly handle a reasoning block if one ever appears (a future
   opt-in, or a provider default changing) — not a new visible
   chain-of-thought feature turned on by this step.
2. **OpenAI's backend migrated from Chat Completions to the Responses API**
   entirely — a different endpoint, a different request shape (`input` items
   instead of `messages`, a top-level `instructions` string instead of a
   system message, flat tool defs, `function_call_output` items keyed by
   `call_id` instead of `{role: "tool"}` messages).
3. **The `Tasks::Base`/`Tasks::Player` class hierarchy is deleted entirely.**
   `Config` now exposes `provider_type`, `model`, `system_prompt` (via a new
   `load_system_prompt`), and four `agent_*` limit readers directly — no more
   per-task settings indirection, no more `Context#task`. `boukensha.rb`
   reads straight from `Config`.
4. **The `mammouth` backend is removed completely** — the file is gone, and
   the `when :mammouth` case is deleted from both `Boukensha.run` and
   `Boukensha.repl`'s backend dispatch.

None of this is mentioned in the README. Since the plan must port what is
*actually there*, this document treats the diff against `ruby/11_tui` as the
source of truth throughout, and calls out anywhere the README undersells or
omits real behaviour. **Flagging this for the user's awareness: updating
`ruby/12_context/README.md` to match its own source is a separate, worthwhile
follow-up, not something this porting plan does** (out of scope — a port
plan ports code, it doesn't rewrite the thing being ported from).

### On dropping `mammouth`

This repo's live testing throughout this session has relied heavily on the
`mammouth`/`claude-haiku-4-5` backend (it's what both `.boukensha/ settings.yaml` files in this environment are configured for). Porting step 12
faithfully means the Python port also drops `mammouth` entirely — matching
Ruby's actual, deliberate removal exactly, not a Python-side improvisation.
This is flagged prominently here because it's a real, user-visible
consequence: after this port, `boukensha.run/repl()` in `python/12_context`
will reject `backend="mammouth"` the same way Ruby's `12_context` rejects
`:mammouth`, and the live settings.yaml files' `provider: mammouth` will need
switching to `anthropic`/`openai`/`gemini`/`ollama`/`ollama_cloud` to run
step 12 at all. Confirm this is actually wanted before implementing — if not,
the fix is a one-line deviation from Ruby (keep `mammouth.rb` and its dispatch
case), which should be a recorded, deliberate choice, not a silent omission
either way.

### A likely upstream bug, ported faithfully but flagged

`Backends::Base#context_window` (an instance method reading the backend's own
per-model table, which — unlike the new top-level `Models` table — genuinely
covers Gemini/OpenAI/Ollama/OllamaCloud models too) is never used for the
value that matters most: `boukensha.rb`'s `run`/`repl` computes
`context_window ||= Models.context_window(model)` **before** the backend
object exists, using the new `lib/boukensha/models.rb`'s `Models::TABLE` —
which lists exactly **three** Claude models and falls back to a conservative
`DEFAULT_CONTEXT_WINDOW = 32_000` for anything else. Configuring `model: gemini-2.5-pro` (context window 1,048,576 in `backends/gemini.rb`'s own
table) would silently compact against a 32,000 budget instead — a ~33×
under-estimate that triggers auto-compaction far too aggressively for any
non-Anthropic model. This plan ports `Models` exactly as written (matching
Ruby bug-for-bug, the porting principle held throughout this series) and
flags it here rather than silently fixing it; whether to file this as a real
bug against the Ruby source is the user's call, separate from this plan.

---

## Part A — Tasks abstraction removed; `Config` absorbs it directly

`lib/boukensha/tasks/{base,player}.rb` are deleted. Their responsibilities
move directly onto `Config`:

| Old (`Tasks::Base`/`Tasks::Player`, via `task_settings`)                     | New (`Config`, direct)                                                                                   |
| ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `Tasks::Player.task_name`                                                        | *(gone — no task-name concept remains)*                                                                 |
| `Tasks::Player.provider(settings)`                                               | `Config#provider_type` → `dig(:tasks, :player, :provider) \|\| "anthropic"`                             |
| `Tasks::Player.model(settings)`                                                  | `Config#model` → `dig(:tasks, :player, :model) \|\| "claude-haiku-4-5"`                                 |
| `Tasks::Player.system_prompt(settings, user_prompts_dir:, default_prompts_dir:)` | `Config#system_prompt` (computed once in `initialize` via a new `load_system_prompt` private method) |
| `Tasks::Base.max_iterations(settings)` (`DEFAULT_MAX_ITERATIONS = 25`)         | `Config#agent_max_iterations` → `dig(:agent, :max_iterations) \|\| 25`                                  |
| `Tasks::Base.max_output_tokens(settings)` (`DEFAULT_MAX_OUTPUT_TOKENS`)        | `Config#agent_max_output_tokens` → `dig(:agent, :max_output_tokens) \|\| 1024`                          |
| *(new)*                                                                          | `Config#agent_max_turn_tokens` → `dig(:agent, :max_turn_tokens) \|\| 60_000`                            |
| *(new)*                                                                          | `Config#agent_compaction_threshold` → `dig(:agent, :compaction_threshold) \|\| 0.85`                    |

`Config#load_system_prompt` (new, private, called once from `initialize`):
reads `<config_dir>/prompts/player/system.md` when
`tasks.player.prompt_override.system == true` and that file exists;
otherwise falls back to `<config_dir>/prompts/system.md`; returns `nil` if
neither exists. **Note the directory has changed**: this reads from the
*user's config directory* (`~/.boukensha/prompts/...`), not a step-bundled
default — `Config::PROMPTS_DIR` (the step-shipped `prompts/` fallback used by
every prior step) is deleted, and `python/12_context` correspondingly ships
**no `prompts/system.md` of its own** (confirmed: `ruby/12_context` has no
`prompts/` directory at all). A config directory with no `prompts/system.md`
and no explicit `system:` argument means the agent runs with **no system
prompt** — a real behavioural change from every prior step, faithfully
ported.

`Config#tasks(name)` / `Config#user_prompts_dir` are deleted along with
`PROMPTS_DIR`. `Context` no longer takes a `task:` keyword argument at all
(see Part C).

---

## Part B — Reasoning-block plumbing (passive; thinking stays off by default everywhere)

### Normalized content-block contract (`backends/base.py`, new docstring)

Every backend's `parse_response` now returns:

```python
{"stop_reason": "tool_use" | "end_turn", "content": [<block>, ...]}
```

where each block is one of:

```python
{"type": "reasoning", "text": "...", "signature": "...", "redacted": True|False}  # signature/redacted optional
{"type": "text", "text": "..."}
{"type": "tool_use", "id": ..., "name": ..., "input": {...}}
```

Reasoning blocks come first, matching Anthropic's native ordering.
`signature`/`redacted` are opaque carry-through — round-tripped unchanged by
whichever backend needs them echoed back, never interpreted by callers.
Backends that don't need reasoning echoed back (OpenAI, in this port) drop
those blocks when rebuilding assistant turns.

### Per-backend changes

- **`backends/anthropic.py`**: `parse_response` maps native `thinking` →
  `{"type": "reasoning", "text": ..., "signature": ...}` and
  `redacted_thinking` → `{"type": "reasoning", "text": "", "redacted": True, "signature": ...}` via a new `_normalize_block` helper. The inverse,
  `_assistant_content`, re-emits `reasoning` blocks as native
  `thinking`/`redacted_thinking` blocks (required — the API rejects modified
  thinking blocks when continuing on the same model). Text-only assistant
  turns are still stored as a bare string and pass through unchanged.
- **`backends/gemini.py`**: `generationConfig` gains a `thinkingConfig` built
  by a new `_thinking_config` method — `{"thinkingLevel": "LOW"}` for
  `gemini-3.1-pro-preview-customtools` (full disable unsupported on that
  model), `{"thinkingBudget": 0}` otherwise. Response parsing reads
  `part["thought"]` → a `reasoning` block carrying `part["thoughtSignature"]`;
  `tool_use` blocks also carry a `signature` from `thoughtSignature`. The
  inverse (`_assistant_content` equivalent) re-emits `thoughtSignature` on
  both reasoning and function-call parts when present.
- **`backends/openai.py`**: see Part C — reasoning is parsed from the
  Responses API's `output[]` array (`item["type"] == "reasoning"`, text
  joined from `item["summary"]`), but **dropped** (not echoed back) when
  rebuilding input items, since `reasoning: {"effort": "none"}` means nothing
  needs round-tripping for this backend.
- **`backends/ollama.py` / `backends/ollama_cloud.py`**: the request body
  gains `"think": False` (extended thinking explicitly disabled for local
  models — cheaper, and this step doesn't attempt to support Ollama's
  thinking mode). Response parsing still adds a `reasoning` block from
  `message["thinking"]` when present (defensive — some models emit it
  regardless of the request flag). `model_info` tables for both are updated
  per the current Ruby source's model list (see the exact model-table diffs
  captured during investigation — carry over verbatim rather than
  re-deriving, since these are provider capability facts, not logic).

### `Agent` changes (`agent.py`)

- New `_log_reasoning(content)`: iterates `parsed["content"]`, emits one
  `Logger.reasoning(text=..., redacted=...)` call per `"reasoning"` block,
  skipping empty non-redacted blocks (a redacted block still logs — it tells
  the viewer "the model thought here").
- `_handle_tool_calls`: preamble text accompanying a tool call is now logged
  via a new `Logger.plan(text=...)` call (only if non-empty) *instead of*
  being folded into the placeholder response text; the tool-use placeholder
  text (`"(tool use — N calls)"`) is always logged via `Logger.response(..., usage=response["usage"], stop_reason="tool_use")`.
- `_extract_text` now joins text blocks with `"\n"` instead of `""` — a
  real behavioural change for any multi-block text response.
- `_log_response`/`_normalized_usage` helpers are **deleted**. Every call
  site now calls `self._logger.response(text=..., usage=response.get("usage"), stop_reason=...)` directly with the *raw* per-provider usage dict — no more
  cross-provider usage-key normalization inside `Agent` (that job doesn't
  move anywhere; see Part F, it's dropped from `Logger` too).

---

## Part C — OpenAI backend: Responses API migration

`backends/openai.py` changes its transport target entirely:

- `BASE_URL`: `.../v1/chat/completions` → `.../v1/responses`.
- `_to_messages(system, messages)` → `_to_input(messages)`: no longer builds
  a `messages` array with a leading system message; the system prompt moves
  to a **top-level `instructions` string** on the request payload
  (`instructions=context.system`), and every message becomes one or more
  **input items** (`_to_input` is `flat_map`-shaped in Ruby — each Ruby
  message can expand to zero or more Python list entries, since a tool
  result becomes a `function_call_output` item and an assistant turn with
  tool calls becomes a text item *plus* one `function_call` item per call).
- Tool defs: flat (`{"name":..., "description":..., "parameters": {...}}`),
  no `{"type": "function", "function": {...}}` wrapper.
- Request body: `max_completion_tokens` → `max_output_tokens`; new
  `reasoning={"effort": "none"}`.
- `parse_response`: reads `response["output"]` (a list of typed items —
  `"reasoning"`, `"message"`, `"function_call"`) instead of
  `response["choices"][0]["message"]`. Tool calls are collected separately
  and appended as `tool_use` blocks after the reasoning/text blocks, each
  keyed by `fc["call_id"]` (not an OpenAI `tool_calls[].id`).
- `_assistant_items` (was `_assistant_message`): rebuilds Responses API input
  items instead of a single chat message — one `{"role": "assistant", "content": text}` item for any text, plus one `{"type": "function_call", "call_id":..., "name":..., "arguments":...}` item per tool call. Reasoning
  blocks are dropped here (not needed back, per `reasoning.effort = "none"`).

This is a genuinely different wire protocol, not a parameter tweak — port it
as a rewrite of the OpenAI backend's request/response methods, verified
against a real call (see Verification), not assumed correct by analogy to
the old Chat Completions shape.

---

## Part D — Context window tracking, colour coding, auto-compaction

*(This part matches the Ruby README's own description — the one part of this
step that's actually documented — carried over here for completeness.)*

### `Context` (`context.py`)

- `__init__` drops `task:` entirely, gains `context_window: int = 200_000`
  and `compaction_threshold: float = 0.85`.
- New state: `current_tokens` (int, mutable — the model's last-reported
  `input_tokens`, i.e. window *pressure*), `turn_tokens` (int — cumulative
  input+output *spend* for the current turn, distinct from `current_tokens`).
- New methods: `reset_turn_tokens()` (called at the top of every
  `Agent.run()`), `add_turn_tokens(input, output)`, `update_tokens(n)`
  (sets `current_tokens`), `usage_fraction()` (`current_tokens / context_window`, 0.0 if window is 0), `usage_pct()` (rounded percentage),
  `needs_compaction(threshold=None)` (defaults to `self.compaction_threshold`),
  `compact_messages(target_fraction=0.60)` (drops the oldest ~40% of
  messages, keeping at least 2, resets `current_tokens` to 0, returns the
  drop count), `clear_messages()` gains a `current_tokens = 0` reset too.

### `Agent` (`agent.py`)

- Constructor: `task_settings:` removed; `max_iterations` now defaults
  directly to `MAX_ITERATIONS` (no task lookup); new `max_turn_tokens: int = 0` (0 = disabled).
- `run()`: calls `self._context.reset_turn_tokens()` and a new
  `self._compact_if_needed()` **once, before the loop starts** — matching
  Ruby exactly (compaction happens once per `Agent.run()` call, i.e. once
  per REPL turn, not once per internal tool-use iteration).
- New `_token_limit_reached()` check inside the loop, alongside the existing
  iteration check — two independent ceilings, whichever trips first triggers
  the same wind-down path (`_wrap_up`), now passing a `"max_tokens"` reason.
- New `_record_usage(response)`: called after every API response —
  `context.add_turn_tokens(usage.get("input_tokens"), usage.get("output_tokens"))` and `context.update_tokens(usage.get( "input_tokens"))`.
- New `_compact_if_needed()`: if `context.needs_compaction()`, calls
  `context.compact_messages()` and logs via `Logger.compaction(before=..., dropped=..., context_window=...)`.
- `Logger.prompt(...)` call gains `context_window=self._context. context_window`.
- `turn_end` calls gain `tokens=self._context.turn_tokens`.

### `Repl` (`repl.py`)

- `__init__` drops `task_settings:`, gains `max_turn_tokens: int | None = None`, passed through to `Agent`.
- New `/compact` command in `handle_command`: calls
  `context.compact_messages()`, outputs `"(compacted context — N messages dropped)"`, returns `"command"`. Added to `HELP` text.

### `boukensha/__init__.py`

- `run()`/`repl()` gain `context_window: int | None = None`.
- `system`/`model`/`backend` now resolved from `cfg.system_prompt` /
  `cfg.model` / `cfg.provider_type` directly (no `task_class`/
  `task_settings` — Part A).
- `context_window = context_window or Models.context_window(model)`
  (Part E note applies — the incomplete lookup table).
- `Context(...)` construction drops `task=`, gains `context_window=..., compaction_threshold=cfg.agent_compaction_threshold`.
- `effective_max_iterations`/`effective_max_output_tokens` locals are
  replaced by direct `cfg.agent_max_iterations` /
  `(max_output_tokens or cfg.agent_max_output_tokens)` reads; a new
  `max_turn_tokens=cfg.agent_max_turn_tokens` is threaded through to both
  `Logger`'s snapshot and `Agent`'s/`Repl`'s constructors.
- `mammouth` removed from `_API_KEY_ENV` and `_build_backend`'s dispatch
  (Part, "On dropping mammouth" above).

### `boukensha/tui.py`

- New colour thresholds: `CTX_WARN_PCT = 70`, `CTX_ALERT_PCT = 85`; a new
  `_ctx_color(pct)` helper (`"bright_black"` below 70%, `"yellow"` 70–84%,
  `"red"` at 85%+).
- Drops its own `_session_input_tokens`/`_session_output_tokens` counters —
  the progress and status lines now read `context.current_tokens` /
  `context.context_window` / `context.usage_pct()` directly from the shared
  `Context`, rather than accumulating a separate parallel total in the TUI.
  This is a simplification worth carrying over exactly — one source of
  truth for "how full is the window" instead of two.
- Progress line (idle state): `"[ready]  ctx {used}/{max} ({pct}%)  {n} turns"`, coloured by `_ctx_color(pct)`.
- Status line: gains `{used}/{max} ({pct}%)` and a `"⚠"` marker when
  `pct >= CTX_ALERT_PCT`.
- New `"compaction"` case in `_handle_event`: appends `"[context compacted — N messages dropped to free space]"` to the log. **No new case for
  `"reasoning"` or `"plan"` events** — Ruby's TUI doesn't render those
  specially either (confirmed: no such branch added to `handle_event` in
  `tui.rb`); they're logged to the JSONL only. Faithful to port as-is —
  surfacing them in the TUI would be a legitimate future enhancement, not
  something to add unasked here.
- Minor: textarea/input width is now recomputed as `width - len(Repl.PROMPT)` on mount and on resize (Ruby fixes a width-off-by-prompt-
  length bug here — carry the fix over, it's a real correctness fix, not a
  new feature).

---

## Part E — `models.py` (new file)

Direct port of `models.rb`:

```python
TABLE = {
    "claude-opus-4-8":   {"context_window": 200_000},
    "claude-sonnet-4-6": {"context_window": 200_000},
    "claude-haiku-4-5":  {"context_window": 200_000},
}
DEFAULT_CONTEXT_WINDOW = 32_000

def context_window(model: str) -> int:
    return TABLE.get(str(model), {}).get("context_window", DEFAULT_CONTEXT_WINDOW)
```

Ported exactly, including its incompleteness relative to each backend's own
per-model table (see "A likely upstream bug" above) — this plan does not
silently enrich the table with the other backends' `context_window` values,
since that would be a Python-side improvement the Ruby source doesn't have,
and the point of this port series is fidelity, not opportunistic fixes.

---

## Part F — `Logger` simplification (`logger.py`)

`Logger.response(...)` drops `task:`/`backend:` parameters entirely, along
with the private helpers that only existed to serve them:
`_execution_metadata`, `_task_name`, `_provider_name`, `_usage_tokens`,
`_first_integer`, `_estimate_cost`. The `usage` dict is now logged **raw**
(whatever shape the backend's `parse_response` attached to
`response["usage"]`), with no cross-provider key normalization and no
per-response cost estimate. `session_start` (from the constructor snapshot)
remains the only place `model`/`provider` are recorded per session — this is
a real reduction in per-response log richness (no more `input_tokens`/
`output_tokens`/`cost_usd` fields flattened onto every `"response"` event),
ported faithfully rather than preserved as a superset.

Two new methods, both simple `_write_log` wrappers matching the Ruby
originals exactly:

```python
def compaction(self, *, before: int, dropped: int, context_window: int) -> None: ...
def reasoning(self, *, text: str, redacted: bool = False) -> None: ...
def plan(self, *, text: str) -> None: ...
```

`prompt(...)` gains a required `context_window: int` parameter.

---

## New files

1. **`python/12_context/`** — seeded from `python/11_tui` (excluding
   `__pycache__`), the established strategy.
2. **`boukensha/models.py`** — Part E, above.

## Deleted files (relative to the `python/11_tui` seed)

3. **`boukensha/tasks/`** (`__init__.py`, `base.py`, `player.py`) — entirely
   removed, per Part A. Any import of `boukensha.tasks`/`boukensha.Player`
   elsewhere in the seeded tree must be found and removed (grep the seed for
   `Player`/`tasks\.` before considering this step done).
4. **`boukensha/backends/mammouth.py`** — removed, per "On dropping
   mammouth" above (pending confirmation — see Decisions below).
5. **`prompts/system.md`** — removed; `python/12_context` ships no bundled
   default system prompt, matching `ruby/12_context` having no `prompts/`
   directory at all.

## Modified files (mirroring the Ruby `11_tui → 12_context` deltas)

6. **`boukensha/config.py`** — Part A: `provider_type`, `model`,
   `system_prompt` property (computed via `_load_system_prompt` in
   `__init__`), `agent_max_iterations`, `agent_max_output_tokens`,
   `agent_max_turn_tokens`, `agent_compaction_threshold`. Removes `tasks()`,
   `user_prompts_dir`, `PROMPTS_DIR`.
7. **`boukensha/context.py`** — Part D.
8. **`boukensha/agent.py`** — Parts B and D combined (reasoning logging +
   the two-ceiling/compaction changes land in the same file).
9. **`boukensha/backends/base.py`** — Part B's contract docstring (no
   behavioural change to the base class itself beyond documentation, per
   Ruby — confirm this holds for the Python base class too, since Python's
   `Base` may carry logic Ruby's doesn't).
10. **`boukensha/backends/anthropic.py`**, **`gemini.py`**, **`ollama.py`**,
    **`ollama_cloud.py`**, **`openai.py`** — Parts B and C, per backend.
    Model-info table updates (new/removed model entries) are carried over
    verbatim from the current Ruby source rather than re-derived.
11. **`boukensha/logger.py`** — Part F.
12. **`boukensha/repl.py`** — Part D's `/compact` command and
    `max_turn_tokens` threading; `task_settings` param removed.
13. **`boukensha/tui.py`** — Part D's colour coding, compaction notice,
    context-driven token display, textarea-width fix.
14. **`boukensha/__init__.py`** — Part D + Part A wiring combined (see Part
    D's `boukensha/__init__.py` subsection — it's the file where the Task
    removal and the context-window/compaction plumbing both land).
15. **`boukensha/version.py`** — `VERSION = "0.12.0"`.
16. **`pyproject.toml`** — `version = "0.12.0"`; description updated to
    mention context management and extended-thinking support (not just
    "context management" — matching Part 0's finding that the step is
    broader than its own Ruby README admits, this port's *own* README
    should describe it accurately even where the Ruby original doesn't).
17. **`README.md`** — full rewrite, structured to actually cover what's in
    this document's Parts A–F (context tracking *and* reasoning support
    *and* the Task-removal *and* the OpenAI migration *and* the dropped
    `mammouth` backend), rather than reproducing the Ruby README's narrower
    scope. Link back to the Ruby README but explicitly note where this
    Python doc covers more ground because the Ruby source does more than
    its own README says.
18. **`boukensha_loader.py`**, **`examples/example.py`**, **gemspec-analog
    (`pyproject.toml` deps)** — confirmed **unchanged** at the Ruby level
    (both `boukensha_loader.rb` and `examples/example.rb` diffed identical
    between `11_tui` and `12_context`); carry the Python equivalents forward
    with no edits beyond what's already listed above.

---

## Decisions needed before starting

1. **Drop `mammouth` or keep it?** The plan as written faithfully mirrors
   Ruby's removal. Given this environment's live settings.yaml files are
   both configured for `mammouth`, confirm this is genuinely wanted before
   implementation — the alternative (keep `backends/mammouth.py` and its
   dispatch case as a deliberate, documented Python-side deviation) is a
   one-file, low-risk change if preferred instead. - Keep it
2. **`models.py`'s incomplete table** — port as-is (bug-for-bug with Ruby,
   this plan's default), or enrich it in the Python port only (a documented
   divergence, not a silent fix) so non-Anthropic models get correct
   compaction behaviour? Either is defensible; it should be a recorded
   choice. Fix it
3. **README scope** — write the Python `12_context/README.md` to cover the
   full actual feature set (this plan's default, item 17 above), or mirror
   the narrower Ruby README's scope for consistency with the porting
   convention used by every prior step's README (which links back to the
   Ruby README as the "full rationale" source)? Recommended: cover the full
   scope, since linking to a Ruby README that itself undersells the step
   would leave the Python docs equally incomplete.

## Not in scope

- Updating `ruby/12_context/README.md` to match its own source (flagged
  above as a worthwhile separate follow-up).
- Filing/fixing the `Models.context_window` incompleteness in the Ruby
  source itself (Decision 2 covers the Python side only).
- Any change to `mud_manager_mcp`, `Boukensha::MCP`, or the standard tool
  library — this step touches none of them, and none of the MCP work from
  earlier plans needs revisiting here.
- The `patches/bubbletea/` native-extension fix — unrelated, already ported
  (N/A to Python) as part of the `11_tui` plan.

## Verification — results

1. **Byte-compile**: full `12_context` tree, clean. ✅
2. **`Config` unit checks**: empty config dir → all documented defaults
   (`provider_type="anthropic"`, `model="claude-haiku-4-5"`, `system_prompt is
   None`, all four `agent_*` at their defaults); `settings.yaml` overrides for
   every field picked up correctly; `prompt_override.system: true` correctly
   selects the task-scoped file over the flat one; **explicitly confirmed**
   this environment's live `settings.yaml` (`tasks.player.max_iterations:
   100`, set earlier this session) does **not** leak into
   `agent_max_iterations` (still 25) — the two are genuinely separate YAML
   paths, flagged as anticipated. ✅
3. **`Context` unit checks**: `usage_fraction`/`usage_pct` arithmetic at
   several points; `needs_compaction` under/at/above threshold and with an
   explicit override; `compact_messages` drops `ceil(40%)` keeping ≥ 2 (both
   the general case and the small-list floor), resets `current_tokens`;
   `reset_turn_tokens`/`add_turn_tokens` accumulate correctly across multiple
   calls; `clear_messages` resets `current_tokens` too. ✅
4. **`Agent` integration checks** against a fake `Client` (real `Agent`/
   `Context`/`Registry`, faked network call only): iteration ceiling and
   turn-token ceiling each independently trigger the wind-down path with the
   correct `limit_reached` kind; `_compact_if_needed` fires **exactly once**
   per `run()` call (verified against a context already over threshold
   *before* `run()` starts, across multiple internal tool-use iterations —
   only one `compaction` event, not one per iteration); `Logger.reasoning`
   and `Logger.plan` fire with the correct text/redacted flags for synthetic
   reasoning and tool-call-preamble content. ✅
5. **Per-backend reasoning round-trip**: Anthropic normalizes
   `thinking`/`redacted_thinking` → `reasoning` blocks and round-trips them
   back to the exact native shape (signature intact) through
   `to_messages`/`_assistant_content`; Gemini normalizes a `thought` part the
   same way and round-trips through `to_messages`/`_assistant_parts`
   (`thoughtSignature` intact), and its `_thinking_config()` confirmed to
   return `{"thinkingBudget": 0}` by default — thinking off, as designed;
   OpenAI parses a `"reasoning"` output item correctly and confirmed to
   **drop** it when rebuilding input items (only the text survives) — matches
   Ruby's documented behaviour exactly; Ollama's defensive `message["thinking"]`
   parse and its `"think": False` request flag both confirmed. `models.py`'s
   disambiguation confirmed directly: `context_window("anthropic",
   "claude-haiku-4-5") == 200_000` vs. `context_window("mammouth",
   "claude-haiku-4-5") == 1_000_000` — same model name, correctly different
   answers — and confirmed the *live* backend instances (`Anthropic(...)
   .context_window`, `Mammouth(...).context_window`) resolve the same
   disambiguated values, proving the actual runtime path (not just the
   fallback lookup) is correct. ✅
6. **Live backend calls**: **Mammouth** (kept per Decision 1) — full
   `boukensha.run()` round trip against the real API, correct reply. **OpenAI
   Responses API** — could not be verified live; this environment's
   `OPENAI_API_KEY` is a 4-character placeholder (`"lime"`), confirmed via
   the API's own `401` error message quoting it back. The Responses API wire
   format is thoroughly unit-tested instead (#5 above) against response
   shapes matching the documented API structure. **Anthropic** — could not be
   verified live either; the configured `ANTHROPIC_API_KEY` returns `401
   invalid x-api-key`, confirmed independently via a raw `curl` to the same
   endpoint with the identical key (an environment/credentials issue, not a
   code path — Anthropic's reasoning-normalization logic is covered by #5).
7. **Live compaction, real backend** — attempted against Mammouth with a
   deliberately tiny `context_window`/`compaction_threshold` across 4 real
   turns. **Did not fire**, and this surfaced the significant finding
   recorded in "Outcome" above: `Agent._record_usage` (ported exactly from
   Ruby) reads `response["usage"]["input_tokens"]` with no per-provider
   normalization, and Mammouth's raw usage is
   `prompt_tokens`/`completion_tokens`-shaped, so `current_tokens` never
   moves off 0. The compaction *mechanism* itself is separately proven
   correct by #3/#4 above (synthetic usage in the documented shape
   correctly triggers it) — the live test's negative result is real
   information about a design gap, not a failed check to paper over. ✅
   (as a diagnostic — confirms an inherited limitation, doesn't confirm the
   headline feature works for this backend)
8. **TUI colour coding**: headless `run_test()` — all three bands (`<70%`
   grey, `70–84%` yellow, `≥85%` red-with-`⚠`) confirmed by driving
   `context.current_tokens` directly and reading back `_ctx_color(...)` and
   the rendered status-bar content. ✅
9. **`/compact` command**: confirmed through the plain `Repl.handle_command`
   (drops messages, reports the exact count via `on_output`, `/help` text
   includes it) and through the TUI's input box (headless `run_test()`,
   confirms the log shows the compaction notice). ✅
10. **Side-by-side against `bin/12_context_ruby`**, real launchers, no
    hand-built scripts: MUD-over-MCP — both languages register exactly 31
    tools and resolve `look` to the same live room. Banner — this
    environment's live config is `provider: mammouth`, which Ruby's
    `12_context` correctly **rejects** (`Unknown backend :mammouth` —
    confirmed as the expected, designed consequence of Decision 1, not a
    bug) — so a fair banner comparison used a shared working backend
    instead: a local Ollama server (`gpt-oss:20b`, no credentials needed,
    confirmed already running). Both languages produced a **byte-for-byte
    identical banner** (`v0.12.0`, provider/model line, MUD reachability,
    the `/compact` line, `Goodbye.`). The real Python TUI (via
    `bin/12_context_python`, no `--no-tui`) additionally confirmed live:
    `ctx 0/128.0k (0%)` (context window correctly resolved from
    `Ollama.MODELS["gpt-oss:20b"]` via the reordering fix) and `38 tools`
    (31 MUD + 6 FileSystem + 1 Shell), matching step 11's tool count. ✅
11. **Mammouth kept, confirmed** (per Decision 1, the opposite of Ruby):
    `backend="mammouth"` works end-to-end in Python (#6); Ruby's `12_context`
    still rejects it with `Unknown backend :mammouth`, confirmed directly
    (#10) — the deviation is real and working as intended in both
    directions. ✅
