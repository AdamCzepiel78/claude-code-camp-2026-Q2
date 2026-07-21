# 03 · The Prompt Builder (Python port)

Python 3 port of [`ruby/03_prompt_builder`](../../ruby/03_prompt_builder/README.md). Same
design — see the Ruby README for the full backend comparison tables and payload/message/tool
shape examples per provider. This document covers the Python-specific implementation and how it
differs from the Ruby source.

The `PromptBuilder` serializes `Context` into the exact format each LLM API expects, delegating
to whichever **backend** you pass in — `Anthropic`, `Gemini`, `OpenAI`, `Ollama`, or
`OllamaCloud`. `PromptBuilder` never calls an API itself; it only assembles the payload, headers,
and URL a caller would POST.

```
Context (Python objects)
        ↓
PromptBuilder
        ↓
Backend (Anthropic, OpenAI, Gemini, Ollama, or OllamaCloud)
        ↓
API payload (plain dicts and lists)
        ↓
POST to API
```

## New files (vs. step 2)

| File | Purpose |
|---|---|
| `boukensha/prompt_builder.py` | `PromptBuilder` — delegates serialization to the active backend |
| `boukensha/backends/base.py` | Shared backend contract: model validation, cost/context-window lookups |
| `boukensha/backends/anthropic.py` | Anthropic Messages API serialization |
| `boukensha/backends/gemini.py` | Gemini `generateContent` serialization |
| `boukensha/backends/openai.py` | OpenAI Chat Completions serialization |
| `boukensha/backends/ollama.py` | Ollama local `/api/chat` serialization |
| `boukensha/backends/ollama_cloud.py` | Ollama Cloud `/api/chat` serialization |
| `prompts/system.md` | Default system prompt for this step (own text, not `00_config`'s — see below) |

`boukensha/errors.py` gains `UnsupportedModelError` alongside step 2's `UnknownToolError`.
Everything else (`config.py`, `tool.py`, `message.py`, `context.py`, `registry.py`,
`tasks/base.py`, `tasks/player.py`) is an unchanged carry-forward — see "Code layout" below for
exactly which prior step each came from.

## `boukensha.prompt_builder.PromptBuilder`

| Method | Description |
|---|---|
| `PromptBuilder(context, backend)` | Wraps a `Context` and a backend instance |
| `to_messages()` | Delegates message serialization to the backend |
| `to_tools()` | Delegates tool serialization to the backend |
| `to_api_payload(*, max_output_tokens=1024)` | Assembles the complete payload ready to POST |
| `headers()` | Returns the correct headers for the backend |
| `url()` | Returns the correct endpoint URL for the backend |

## Backends

Each backend owns a static `MODELS` table and refuses to construct with a model outside it
(`UnsupportedModelError`), so `settings.yaml` can't silently select an unsupported or misspelled
model. Every entry carries `context_window`, `cost_per_million` (`{"input": ..., "output":
...}`), `usage_unit`, and optionally `usage_level` (Ollama Cloud's usage tier). Backend instances
expose `context_window`, `input_token_cost_per_million`, `output_token_cost_per_million`,
`usage_unit`, `usage_level`, and `estimate_cost(*, input_tokens, output_tokens)`. Local Ollama
models cost `0.0`; Ollama Cloud's plan-based pricing has no per-token cost, so
`estimate_cost` returns `None` there.

| Backend | Endpoint | Auth |
|---|---|---|
| `Anthropic` | `https://api.anthropic.com/v1/messages` | `ANTHROPIC_API_KEY` |
| `Gemini` | `.../v1beta/models/{model}:generateContent` | `GEMINI_API_KEY` |
| `OpenAI` | `https://api.openai.com/v1/chat/completions` | `OPENAI_API_KEY` |
| `Ollama` | `http://localhost:11434/api/chat` | none (local) |
| `OllamaCloud` | `https://ollama.com/api/chat` | `OLLAMA_API_KEY` |

Anthropic and Gemini send the system prompt as a top-level payload field; OpenAI, Ollama, and
OllamaCloud fold it into the messages array as a `role: "system"` entry. See the Ruby README's
"Backends" section for the full side-by-side JSON examples — unchanged by this port.

## Code layout

| File | Purpose | Carried forward from |
|------|---------|------|
| `boukensha/config.py` | `Config` class, incl. `PROMPTS_DIR` | `00_config` (unchanged — see below) |
| `boukensha/tasks/base.py` | Abstract `Base` task | `00_config` (unchanged) |
| `boukensha/tasks/player.py` | Concrete `Player` task | `00_config` (unchanged) |
| `boukensha/tool.py` | `Tool` dataclass | `02_the_registry` (unchanged) |
| `boukensha/message.py` | `Message` dataclass | `02_the_registry` (unchanged) |
| `boukensha/context.py` | `Context` class | `02_the_registry` (unchanged) |
| `boukensha/registry.py` | `Registry` class | `02_the_registry` (unchanged) |
| `boukensha/errors.py` | `UnknownToolError`, new `UnsupportedModelError` | new this step |
| `boukensha/prompt_builder.py` | `PromptBuilder` | new this step |
| `boukensha/backends/*.py` | `Base` + five concrete backends | new this step |
| `boukensha/__init__.py` | Top-level package exports | port of `lib/boukensha.rb` |
| `examples/example.py` | Runnable smoke test | port of `examples/example.rb` |
| `pyproject.toml` | Package metadata + the two runtime dependencies (`python-dotenv`, `PyYAML`) |

## What's different from step 2

- **`Config.PROMPTS_DIR` is back.** Diffing `ruby/00_config/lib/boukensha/config.rb` against
  `ruby/03_prompt_builder/lib/boukensha/config.rb` shows they're **byte-identical** — this step
  re-ships a `prompts/` directory and reintroduces the `PROMPTS_DIR` constant that steps 1 and 2
  dropped. `boukensha/config.py` here is copied straight from `00_config`'s Python port
  unchanged (it already defines `PROMPTS_DIR`), and `tasks/base.py`/`tasks/player.py` are copied
  from `00_config` too (also byte-identical at the Ruby source level). `tool.py`, `message.py`,
  `context.py`, and `registry.py` carry forward from `02_the_registry` instead, since those Ruby
  sources only diverge by a trailing newline.
- **This step's own `prompts/system.md`** is different (shorter, one paragraph) from
  `00_config`'s — not reused, copied from `ruby/03_prompt_builder/prompts/system.md` verbatim.

## Porting notes (deviations from the Ruby source)

Carries forward every convention already established in `00_config`'s, `01_struct_skeleton`'s,
and `02_the_registry`'s READMEs (symbol/string key collapse, `Path`-based paths, `task_name()` as
a classmethod, `Tool`/`Message` as dataclasses, decorator-based `Registry.tool`, full type
hints, no `abc.ABC`, etc.) — not repeated here. New for this step:

- **`Backends.Base.model_info` naming collision.** Ruby overloads `model_info` as both a *class*
  method (`self.model_info(model)`, a `MODELS` table lookup) and an *instance* method
  (`model_info`, the memoized entry set at construction) — legal in Ruby's separate class/
  instance method namespaces, impossible to name identically in Python. The instance-facing name
  stays `model_info` (a property read by every cost/context-window accessor); the classmethod
  lookup is renamed **`model_info_for(model)`**.
- **`validate_model!` → `validate_model`** — a trailing `!` isn't a valid Python identifier,
  same precedent as `prompt_override?` → `prompt_override` in `00_config`.
- **`MODELS` is a plain `ClassVar[dict[str, dict[str, Any]]]`**, not a dataclass/`TypedDict` per
  model entry — consistent with how `Config.settings` and task-settings dicts are handled
  elsewhere in this port. `Base.MODELS` defaults to `None`; `Base.models()` raises
  `NotImplementedError` if a subclass never overrides it, mirroring the
  `Tasks.Base.task_name()` "subclass must override" pattern already used elsewhere.
- **`usage_unit`/`usage_level` stay plain `str`**, not an enum — same reasoning already applied
  to `Message.role`: Ruby never validates these symbols, so a plain string is the most direct 1:1
  port.
- **A real latent bug in the Ruby source is ported faithfully, not fixed:**
  `PromptBuilder#to_messages` calls `backend.to_messages(context.messages)` — **one** argument.
  `Anthropic.to_messages`/`Gemini.to_messages` take exactly one argument and work fine through
  this path. `OpenAI.to_messages`, `Ollama.to_messages`, and `OllamaCloud.to_messages` are
  defined as `to_messages(system, messages)` — **two** arguments — because those three backends
  fold the system prompt into the messages array instead of a top-level field. Calling
  `PromptBuilder.to_messages()` (not `to_api_payload()`) against one of those three backends
  raises a `TypeError` here, exactly as it raises Ruby's `ArgumentError` on the identical call.
  **`examples/example.rb`/`example.py` never trigger this** — both only call `to_api_payload()`,
  which routes through each backend's own `to_payload`, which correctly calls its own
  `to_messages` with the right arity internally. Ported as-is (not normalized) to keep this port
  a faithful mirror of the actual Ruby behavior, same philosophy already applied to doc/code
  drift noted in `01_struct_skeleton`'s plan.
- **Provider→backend dispatch in `example.py`** is a plain `if`/`elif` chain reading
  `os.environ["..._API_KEY"]` (raises `KeyError` if unset), matching Ruby's `case`/`when` +
  `ENV.fetch` without a default as closely as Python allows.
- **`boukensha/backends/__init__.py`** re-exports all five backend classes plus `Base`. The
  top-level `boukensha/__init__.py` does **not** flatten them in — callers reach backends via
  `boukensha.backends.Anthropic` (or `boukensha.backends.anthropic.Anthropic`), matching Ruby's
  `Boukensha::Backends::Anthropic` namespacing rather than `Boukensha::Anthropic`.

## Shared venv, no per-step install

Same as prior steps: `python/.venv` is shared only for the two third-party runtime deps
(`python-dotenv`, `PyYAML`). This step's own `boukensha` package is never `pip install`-ed —
`examples/example.py` loads it via `sys.path` insertion instead, mirroring Ruby's per-step
`require_relative "../lib/boukensha"`.

## Setup

Requires Python ≥ 3.11.

```bash
cd week1_baseline/python
python3 -m venv .venv
source .venv/bin/activate
pip install "python-dotenv>=1.0" "PyYAML>=6.0"
```

## Run example

```bash
./week1_baseline/bin/03_prompt_builder_python
```

This bootstraps `python/.venv` on first run and is safe to re-run any time. Or, with the shared
venv active:

```bash
python 03_prompt_builder/examples/example.py
```

Expected output (values from your `.boukensha/`, assuming `provider: anthropic`):

```
=== BOUKENSHA Step 3: Prompt Builder ===

Config: #<Boukensha.Config dir=/home/andrew/Sites/Claude-Code-Camp/.boukensha tasks=player>
Provider: anthropic
Model: claude-haiku-4-5
{
  "model": "claude-haiku-4-5",
  "system": "You are a MUD player assistant. Use the tools available to you to help the player explore, fight, and interact with the world.",
  "max_tokens": 1024,
  "tools": [
    {
      "name": "look",
      "description": "Look around the current room for details",
      "input_schema": { "type": "object", "properties": {}, "required": [] }
    },
    {
      "name": "move",
      "description": "Move the player in a direction (north, south, east, west, up, down)",
      "input_schema": {
        "type": "object",
        "properties": { "direction": { "type": "string", "description": "The direction to move" } },
        "required": ["direction"]
      }
    }
  ],
  "messages": [
    { "role": "user", "content": "I just arrived in the dungeon. What's around me, and can you move north?" },
    { "role": "assistant", "content": "Let me take a look around first." },
    {
      "role": "user",
      "content": [
        {
          "type": "tool_result",
          "tool_use_id": "toolu_01X",
          "content": "A damp stone corridor stretches north. Torches flicker on the walls."
        }
      ]
    }
  ]
}
```
