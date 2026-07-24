# Plan: Port `ruby/03_prompt_builder` to Python

## Goal

Port `week1_baseline/ruby/03_prompt_builder` into `week1_baseline/python/03_prompt_builder/`
(directory doesn't exist yet). This step adds the **Prompt Builder** — a `PromptBuilder` that
delegates `Context` serialization to a pluggable **backend** (`Anthropic`, `Gemini`, `OpenAI`,
`Ollama`, `OllamaCloud`), each of which knows its own API's message/tool/payload shape, model
table, and cost estimation. It carries forward every convention established in `00_config`,
`01_struct_skeleton`, and `02_the_registry` (see those three plans and their READMEs' "Porting
notes" sections) — this plan only calls out what's new or different for step 3.

## Reference files (what to port from)

| Ruby file                                                              | Role                                                                                                     |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| `week1_baseline/ruby/03_prompt_builder/README.md`                      | Spec for this step — backend comparison tables, payload/message/tool-shape examples per provider           |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha/prompt_builder.rb`| `PromptBuilder` class: `initialize(context, backend)`, `to_messages`, `to_tools`, `to_api_payload`, `headers`, `url` |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha/errors.rb`        | Adds `UnsupportedModelError` alongside step 2's `UnknownToolError`                                          |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha/backends/base.rb` | Shared backend contract: `MODELS`-based model validation/lookup, cost estimation                            |
| `.../backends/anthropic.rb`                                            | Anthropic Messages API serialization (`system` top-level, tool_result as user message)                     |
| `.../backends/gemini.rb`                                               | Gemini `generateContent` serialization (`role: "model"`, `functionResponse`/`functionDeclarations`)         |
| `.../backends/openai.rb`                                               | OpenAI Chat Completions serialization (`function`-wrapped tools, `role: system` message)                    |
| `.../backends/ollama.rb`                                               | Ollama local `/api/chat` serialization (same shape family as OpenAI, no API key)                            |
| `.../backends/ollama_cloud.rb`                                         | Ollama Cloud `/api/chat` serialization (same shape family, requires `OLLAMA_API_KEY`)                       |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha/config.rb`        | **Byte-identical to `00_config`'s `config.rb`** (confirmed via diff) — `PROMPTS_DIR` is back              |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha/tasks/base.rb`    | **Byte-identical to `00_config`'s `tasks/base.rb`**                                                        |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha/tasks/player.rb`  | **Byte-identical to `00_config`'s `tasks/player.rb`**                                                      |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha/tool.rb`          | Unchanged from `02_the_registry` (only a trailing-newline diff)                                             |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha/message.rb`       | Unchanged from `02_the_registry`                                                                            |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha/context.rb`       | Unchanged from `02_the_registry`                                                                            |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha/registry.rb`      | Unchanged from `02_the_registry`                                                                            |
| `week1_baseline/ruby/03_prompt_builder/prompts/system.md`              | **Different text from `00_config`'s `prompts/system.md`** — shorter, one paragraph; use this step's own copy verbatim |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha.rb`               | Top-level require wiring (adds `prompt_builder`, `backends/*` requires)                                     |
| `week1_baseline/ruby/03_prompt_builder/examples/example.rb`            | Runnable smoke test — registers `look`/`move` tools, adds 3 messages, picks a backend from `provider`, prints `to_api_payload` as pretty JSON |
| `week1_baseline/python/00_config/boukensha/config.py`                  | Source to copy `config.py` from directly — already has `PROMPTS_DIR`, no reconstruction needed             |
| `week1_baseline/python/00_config/boukensha/tasks/{base,player}.py`     | Source to copy `tasks/base.py`/`tasks/player.py` from directly                                              |
| `week1_baseline/python/02_the_registry/boukensha/{tool,message,context,registry}.py` | Source to copy the four unchanged structs/registry from directly                                |

## What's different from step 2 (read before porting)

- **`Config.PROMPTS_DIR` is back.** Diffing `ruby/00_config/lib/boukensha/config.rb` against
  `ruby/03_prompt_builder/lib/boukensha/config.rb` shows they are **byte-identical** — this step
  re-ships a `prompts/` directory and reintroduces the `PROMPTS_DIR` constant that steps 1 and 2
  dropped. Concretely: copy `python/00_config/boukensha/config.py` forward unchanged (it already
  defines `PROMPTS_DIR: Path = Path(__file__).resolve().parent.parent / "prompts"`), and ship
  this step's own `prompts/system.md` (different, shorter text than `00_config`'s — see above).
  `tasks/base.py` and `tasks/player.py` are also byte-identical to `00_config`'s and copy forward
  unchanged too.
- **`tool.py`, `message.py`, `context.py`, `registry.py` carry forward unchanged from
  `02_the_registry`** — the Ruby sources only differ by a trailing newline (non-substantive).
- **`errors.rb` gains `UnsupportedModelError`** alongside `UnknownToolError`, raised by
  `Backends::Base.validate_model!` when a `settings.yaml` model isn't in a backend's `MODELS`
  table.
- **New `backends/` subpackage** — five backend classes sharing a `Base` contract. Each backend:
  - owns a static `MODELS` table (model name → `context_window`, `cost_per_million` {`input`,
    `output`}, `usage_unit`, optionally `usage_level` and `advertised_context_window`);
  - refuses to construct with an unsupported model (`validate_model!` at `initialize` time via
    `configure_model`);
  - implements `to_messages`, `to_tools`, `to_payload`, `headers`, `url` in its own API's shape.
  - exposes `context_window`, `input_token_cost_per_million`, `output_token_cost_per_million`,
    `usage_unit`, `usage_level`, `estimate_cost(input_tokens:, output_tokens:)` (returns `nil`/
    `None` when either cost is unknown, e.g. Ollama Cloud's plan-based pricing).
- **`PromptBuilder` is a thin delegator** in front of whichever backend is passed in — it never
  calls an API itself, only assembles the payload/headers/url.
- **A real latent bug/inconsistency in the Ruby source, carried over if ported faithfully:**
  `PromptBuilder#to_messages` calls `@backend.to_messages(@context.messages)` — **one** argument.
  `Anthropic#to_messages`/`Gemini#to_messages` take exactly one argument (`messages`) and work
  fine through this path. But `OpenAI#to_messages`, `Ollama#to_messages`, and
  `OllamaCloud#to_messages` are defined as `to_messages(system, messages)` — **two** arguments —
  because those three backends inline the system prompt as a `role: "system"` message rather than
  a top-level payload field. Calling `PromptBuilder#to_messages` (not `to_api_payload`) against
  an OpenAI/Ollama/OllamaCloud backend would raise Ruby's `ArgumentError: wrong number of
  arguments (given 1, expected 2)`. **This is never triggered by `examples/example.rb`** — it
  only ever calls `builder.to_api_payload`, which routes through each backend's own `to_payload`
  (which correctly calls its own `to_messages` with the right arity internally). Flagged as an
  open question below: port this faithfully (the bug reproduces 1:1 for 3 of 5 backends) or
  normalize it.

## Target layout

```
week1_baseline/python/03_prompt_builder/
  boukensha/
    __init__.py            # exports Config, Player, Tool, Message, Context, Registry,
                            #   PromptBuilder, UnknownToolError, UnsupportedModelError
    config.py                # unchanged copy from 00_config (has PROMPTS_DIR)
    tool.py                   # unchanged copy from 02_the_registry
    message.py                # unchanged copy from 02_the_registry
    context.py                 # unchanged copy from 02_the_registry
    registry.py                 # unchanged copy from 02_the_registry
    errors.py                    # UnknownToolError + new UnsupportedModelError
    prompt_builder.py              # new — PromptBuilder
    backends/
      __init__.py                  # exports Base, Anthropic, Gemini, Ollama, OllamaCloud, OpenAI
      base.py                        # new — Base backend contract
      anthropic.py                    # new
      gemini.py                        # new
      openai.py                         # new
      ollama.py                          # new
      ollama_cloud.py                     # new
    tasks/
      __init__.py
      base.py               # unchanged copy from 00_config
      player.py             # unchanged copy from 00_config
  examples/
    example.py             # from examples/example.rb
  prompts/
    system.md                # this step's own text (not 00_config's)
  README.md                 # adapted from ruby README + "porting notes" section (per established precedent)
  pyproject.toml
```

## Porting decisions (new for this step)

- **`Backends::Base.model_info` naming collision.** Ruby has both a *class* method
  `self.model_info(model)` (looks up an entry in `MODELS`) and an *instance* method `model_info`
  (no args, returns the memoized `@model_info` set by `configure_model`) — legal in Ruby because
  class methods and instance methods are separate namespaces. Python has no such split; a
  `@classmethod` and a `@property` can't share one name on the same class. **Decision: keep the
  instance-facing name as `model_info` (used far more often — every cost/window accessor reads
  `self.model_info`), rename the classmethod lookup to `model_info_for(model)`.** Flagged as an
  open question below in case the reverse naming is preferred.
- **`validate_model!` → `validate_model`** — trailing `!` isn't a valid Python identifier,
  consistent with the already-established `prompt_override?` → `prompt_override` precedent from
  `00_config`.
- **`MODELS` stays a plain `dict[str, dict[str, Any]]` class attribute** (`ClassVar[dict[str,
  dict[str, Any]]]`), not a dataclass/TypedDict per model entry — consistent with how
  `Config.settings` and task-settings dicts are already handled elsewhere in this port (plain
  dicts, not modeled types), and this data is only ever stored/read, never constructed
  piecemeal. `Base.MODELS` itself defaults to an unset sentinel; `Base.models()` (classmethod)
  raises `NotImplementedError` if a subclass never defines its own `MODELS`, mirroring the
  `Tasks.Base.task_name()` pattern already used for the same "subclass must override" shape.
- **`usage_unit`/`usage_level` stay plain `str`** (`"tokens"`, `"local_compute"`,
  `"ollama_cloud_usage"`, `"medium"`, `"high"`), not an enum — same reasoning already applied to
  `Message.role` in `01_struct_skeleton`: Ruby never validates these symbols, so a plain string
  is the most direct 1:1 port.
- **`estimate_cost(*, input_tokens, output_tokens)`** returns `None` when either
  `input_token_cost_per_million`/`output_token_cost_per_million` is `None` (Ollama Cloud's
  `cost_per_million: { input: nil, output: nil }`), otherwise the same weighted formula as Ruby.
- **Provider→backend dispatch in `examples/example.py`** ports the Ruby `case`/`when` chain as a
  plain `if`/`elif` (or a small `dict[str, type[Base]]` lookup) keyed on the `provider` string
  from `settings.yaml`; each branch reads its API key via `os.environ["..._API_KEY"]` (raises
  `KeyError` if unset, matching Ruby's `ENV.fetch` without a default).
- **`boukensha/backends/__init__.py`** re-exports all five backend classes plus `Base`, mirroring
  how `lib/boukensha.rb` requires every `backends/*.rb` file at the top level (but the Python
  top-level `boukensha/__init__.py` does **not** flatten backend classes into itself — callers
  reach them via `boukensha.backends.anthropic.Anthropic` or the `boukensha.backends` re-export,
  matching Ruby's `Boukensha::Backends::Anthropic` namespacing rather than `Boukensha::Anthropic`).

## Open questions

1. **Port the `PromptBuilder#to_messages`/backend arity mismatch faithfully, or normalize it?**
   Recommendation: **port faithfully** — `PromptBuilder.to_messages()` calls
   `self._backend.to_messages(self._context.messages)` exactly as Ruby does, which will raise a
   `TypeError` (Python's equivalent of Ruby's `ArgumentError`) if called against `OpenAI`,
   `Ollama`, or `OllamaCloud`. This matches the project's established practice elsewhere (see
   `python_port_01_struct_skeleton.md`'s handling of the `Context`/README `token_budget` drift)
   of treating the actual Ruby code as the source of truth and calling out drift/bugs in the
   Python README's porting notes rather than silently fixing them. The alternative is to give
   every backend's `to_messages` a uniform signature (e.g. all take `(system, messages)`, with
   `Anthropic`/`Gemini` ignoring `system`) so `PromptBuilder.to_messages()` works uniformly across
   all five backends — a genuine behavioral improvement, but a deviation from "mirror the Ruby
   source." Which do you want?
2. **`Backends.Base.model_info` naming** (see "Porting decisions" above) — OK with instance
   property `model_info` + classmethod `model_info_for(model)`, or would you rather keep the
   classmethod named `model_info` and rename the instance accessor instead (e.g.
   `current_model_info`)?
3. **Provider dispatch shape in `example.py`** — plain `if`/`elif` chain (closest 1:1 to Ruby's
   `case`/`when`), or a `dict[str, type[Base]]` lookup table? Either is a small, contained
   decision inside a fully-owned file, but flagging in case you have a preference — recommend
   `if`/`elif` for the closest match to the Ruby control flow being ported.

## Suggested execution order (once questions are answered)

1. Scaffold `python/03_prompt_builder/` (package dirs including `backends/`, `pyproject.toml`),
   using the same shared `python/.venv` convention as prior steps (no per-step editable install).
2. Copy `config.py` from `00_config` and `tasks/base.py`/`tasks/player.py` from `00_config`
   unchanged; copy `tool.py`/`message.py`/`context.py`/`registry.py` from `02_the_registry`
   unchanged. Copy this step's own `prompts/system.md` (not `00_config`'s).
3. Write `errors.py` (`UnknownToolError`, `UnsupportedModelError`).
4. Write `backends/base.py` (`Base`: `models()`, `model_info_for()`, `validate_model()`,
   `configure_model()`, `model_info` property, `context_window`, `input_token_cost_per_million`,
   `output_token_cost_per_million`, `usage_unit`, `usage_level`, `estimate_cost()`), per the
   answered open questions.
5. Write the five concrete backends (`anthropic.py`, `gemini.py`, `openai.py`, `ollama.py`,
   `ollama_cloud.py`), porting each `MODELS` table, `to_messages`, `to_tools`, `to_payload`,
   `headers`, `url` verbatim from the corresponding `.rb` file.
6. Write `prompt_builder.py` (`PromptBuilder`: `to_messages`, `to_tools`, `to_api_payload`,
   `headers`, `url`), per Q1's answer.
7. Update `boukensha/__init__.py` and `boukensha/backends/__init__.py` exports.
8. Port `examples/example.py`: build `Context` + `Registry`, register `look`/`move`, add the
   three example messages, dispatch to a backend per `provider` (Q3's answer), print
   `Config`/`provider`/`model`/pretty-printed `to_api_payload()` JSON — run against the existing
   `week1_baseline/.boukensha/settings.yaml` and compare output against
   `ruby/03_prompt_builder/examples/example.rb`'s actual output (via `bin/03_prompt_builder`) for
   parity.
9. Write `python/03_prompt_builder/README.md` (design doc + porting-notes section — including the
   `PROMPTS_DIR` return, the arity-mismatch note from Q1, and the `model_info` naming split from
   Q2), per the established precedent.
10. Add `bin/03_prompt_builder_python`, consistent with `bin/02_the_registry_python` and the
    existing `bin/03_prompt_builder` (Ruby) naming already in the repo — installing only the
    shared deps into `python/.venv`.
