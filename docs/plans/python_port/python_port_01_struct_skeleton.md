# Plan: Port `ruby/01_struct_skeleton` to Python

## Goal

Port `week1_baseline/ruby/01_struct_skeleton` into `week1_baseline/python/01_struct_skeleton/`
(directory doesn't exist yet). This step adds three plain data structures — `Tool`, `Message`,
`Context` — on top of the `Config`/`Tasks` machinery already ported in `00_config`. It carries
forward the package layout, naming, and porting conventions established there (see
`docs/plans/00_python_port/python_port.md` and `week1_baseline/python/00_config/README.md`'s
"Porting notes" section) — this plan only calls out what's new or different for step 1.

## Reference files (what to port from)

| Ruby file                                                                | Role                                                                                                                                                                                                     |
| ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `week1_baseline/ruby/01_struct_skeleton/README.md`                     | Spec for this step — field tables and`to_s` display format for `Tool`, `Message`, `Context`                                                                                                     |
| `week1_baseline/ruby/01_struct_skeleton/lib/boukensha/tool.rb`         | `Tool` struct: `name`, `description`, `parameters`, `block`                                                                                                                                    |
| `week1_baseline/ruby/01_struct_skeleton/lib/boukensha/message.rb`      | `Message` struct: `role`, `content`, `tool_use_id`                                                                                                                                               |
| `week1_baseline/ruby/01_struct_skeleton/lib/boukensha/context.rb`      | `Context` class: holds `task`, `system`, `messages`, `tools`; `register_tool`, `add_message`, `tool_count`, `turn_count`                                                               |
| `week1_baseline/ruby/01_struct_skeleton/lib/boukensha/config.rb`       | Same as step 0's`Config` **except `PROMPTS_DIR` constant is removed** — see notes below                                                                                                       |
| `week1_baseline/ruby/01_struct_skeleton/lib/boukensha/tasks/base.rb`   | **Byte-identical** to step 0's `tasks/base.rb` (diffed, no changes)                                                                                                                              |
| `week1_baseline/ruby/01_struct_skeleton/lib/boukensha/tasks/player.rb` | **Byte-identical** to step 0's `tasks/player.rb`                                                                                                                                                 |
| `week1_baseline/ruby/01_struct_skeleton/lib/boukensha.rb`              | Top-level require wiring (adds`tool`, `message`, `context` requires)                                                                                                                               |
| `week1_baseline/ruby/01_struct_skeleton/examples/example.rb`           | Runnable smoke test — builds a`Context`, registers a `move` tool, adds two messages, prints `Config`, `Context`, `Tool`, `Messages`                                                         |
| `week1_baseline/ruby/01_struct_skeleton/Gemfile`                       | Unchanged from step 0 (`dotenv` only)                                                                                                                                                                  |
| `week1_baseline/python/00_config/` (the already-ported step 0)         | Source for the files that carry forward unchanged/near-unchanged:`config.py` (minus `PROMPTS_DIR`), `tasks/base.py`, `tasks/player.py`, plus the established package/README/launcher conventions |

## What's different from step 0 (read before porting)

- **`Config::PROMPTS_DIR` is dropped.** Diffing `ruby/00_config/lib/boukensha/config.rb` against
  `ruby/01_struct_skeleton/lib/boukensha/config.rb` shows only the `PROMPTS_DIR` constant (and
  its requiring comment) removed — everything else in `Config` is identical. There is also no
  `prompts/` directory shipped in `ruby/01_struct_skeleton` at all, and `examples/example.rb`
  calls `Tasks::Player.system_prompt(player_settings, user_prompts_dir: config.user_prompts_dir)`
  **without** a `default_prompts_dir:` argument — so `system_prompt` resolves to `nil` unless the
  user has their own `.boukensha/prompts/player/system.md` override. The Python port should match
  this exactly: no `PROMPTS_DIR`, no shipped `prompts/system.md`, `system_prompt` called without
  `default_prompts_dir`.
- **`tasks/base.rb` and `tasks/player.rb` are untouched** — confirmed via diff against step 0.
  The Python `tasks/base.py` and `tasks/player.py` already ported for `00_config` can be copied
  forward as-is (still dropping the `?` suffix, still classmethod-based `task_name()`, etc. —
  same conventions already decided for step 0).
- **README/code drift in `Context`**: the step's README documents a `token_budget` field and
  shows example `to_s` output like `#<Context turns=2 tools=1 budget=8192>` — but the actual
  `context.rb` has no `token_budget` field, no `add_message`/`register_tool` budget tracking, and
  its real `to_s` is `"#<Context task=#{task&.task_name} turns=#{turn_count} tools=#{tool_count}>"`
  (no budget at all, but *does* include `task`, which the README's example strings omit). The code
  is the source of truth — the README table looks aspirational/stale (consistent with
  `ITERATIONS.md`'s own admission elsewhere that AI-driven edits regressed some docs/code in this
  area). **Plan is to port the actual `context.rb` behavior**, not the README's field table —
  flagged as an open question below in case you want the Python version to also carry the
  (currently unused) `token_budget` field for forward-compatibility.

## Target layout

```
week1_baseline/python/01_struct_skeleton/
  boukensha/
    __init__.py          # exports Config, Player, Tool, Message, Context
    config.py             # ported from 00_config, PROMPTS_DIR removed
    tool.py                # new — Tool
    message.py             # new — Message
    context.py             # new — Context
    tasks/
      __init__.py
      base.py               # unchanged copy from 00_config
      player.py             # unchanged copy from 00_config
  examples/
    example.py             # from examples/example.rb
  README.md                 # adapted from ruby README + "porting notes" section (per 00_config precedent)
  pyproject.toml
```

No `prompts/` directory in this step (see above).

## Porting decisions (new for this step)

- **`Tool` and `Message`** (plain data, no behavior beyond display) → `@dataclass` (mutable, not
  frozen — matches Ruby `Struct`'s mutability and default field-wise `__eq__`). Each gets a
  `__repr__` matching the Ruby `to_s` format as closely as sensible in Python:
  - `Tool`: `description` truncated to the first 40 chars (`description.to_s[0..40]` — Ruby's
    range is inclusive, i.e. 41 chars — porting as `description[:41]`), `parameters.keys()`
    rendered as a Python list, e.g. `params=['direction']` instead of Ruby's symbol-list
    `params=[:direction]` (unavoidable, cosmetic-only difference — Python dict keys from a
    JSON-schema-shaped `parameters` dict are always strings).
  - `Message`: content truncated to 60 chars + literal `...`, with a `[tool_use_id]` tag inserted
    after `role` when `tool_use_id` is set — direct port of the Ruby `to_s`.
  - `Tool.block` and any executable/callable field types as `Callable[..., Any]` — stored, not
    invoked, in this step (dispatch comes in step 2's Tool Registry).
- **`Context`** → plain class (not a dataclass, since it owns mutable collections and behavior),
  carrying forward `Config`'s established style: `self.task`, `self.system`, `self.messages: list[Message] = []`,
  `self.tools: dict[str, Tool] = {}`, methods `register_tool(tool)`, `add_message(role, content, *, tool_use_id=None)`,
  properties `tool_count`/`turn_count`, and `__repr__` matching `context.rb`'s actual `to_s`
  (includes `task`, not `budget`).
- **`role`** (`Message.role`, and the `role`/`content` args to `add_message`) — Ruby passes Ruby
  symbols (`:user`, `:assistant`, `:tool_result`) at the call sites. Two ways to carry this into
  Python, both reasonable — see open questions.
- **`Config`, `tasks/base.py`, `tasks/player.py`** carry forward the conventions already decided
  and documented in `python/00_config/README.md`'s "Porting notes" (symbol/string dual-key
  collapse, `prompt_override?` → `prompt_override`, `Path`-based `dir`, `task_name()` staying a
  classmethod that raises `NotImplementedError`, full type hints, no `abc.ABC`). Not re-litigated
  here.

## Open questions

1. **Shared-venv package-name collision.** `python/00_config`'s `bin/00_config_python` launcher
   runs `pip install -e ./00_config` into the shared `python/.venv`. That package's import name
   is `boukensha`. If `python/01_struct_skeleton` also ships its own `boukensha` package and its
   launcher does the same `pip install -e ./01_struct_skeleton`, **the two editable installs
   collide on the same top-level import name** in one shared venv — behavior is undefined/fragile
   (whichever was installed most recently tends to win, silently shadowing the other step's code).
   This wasn't a problem when only one step existed. Ruby doesn't have this problem because each
   step is loaded via `require_relative` from within its own directory — no shared "gem
   environment" until step 9 (global executable), which `ITERATIONS.md` says the Python port
   skips entirely. Recommended fix, matching that Ruby model: **stop `pip install -e`-ing each
   step's own `boukensha` package.** Keep `python/.venv` shared **only** for the two genuine
   third-party dependencies (`python-dotenv`, `PyYAML`); each step's own code loads purely via the
   `sys.path.insert(...)` fallback already present in `00_config`'s `examples/example.py` (which
   mirrors Ruby's `require_relative "../lib/boukensha"`). This would mean retroactively adjusting
   `00_config`'s `bin/00_config_python` launcher too (drop its `pip install -e ./00_config` step).
   **OK to make that change as part of this port?** (If not, the alternative is giving each step's
   package a unique distribution *and* import name, e.g. `boukensha_01_struct_skeleton` — a bigger
   departure from Ruby's consistent `Boukensha` namespace.)
2. **`Context.token_budget`** — port only what `context.rb` actually implements (no budget field,
   `to_s` shows `task`/`turns`/`tools` only), leaving the README's `budget=`/`used=` examples as
   known doc/code drift (noted in the Python README same as this plan does)? Or add an unused
   `token_budget` field now, anticipating it lands for real in a later step? Recommendation: port
   the code as-is (no budget field) — simplest, matches what step 1 actually ships, avoids
   guessing at a shape that may change once it's really implemented.
3. **`role` typing** — plain `str` (loosest, most direct 1:1 port of Ruby's untyped symbols), or
   an `enum.StrEnum` (`Role.USER`, `Role.ASSISTANT`, `Role.TOOL_RESULT`) for real type safety and
   IDE autocomplete? `StrEnum` is more idiomatic "professional Python" and was the spirit of your
   earlier ask, but it's a real behavioral deviation (Ruby never validates the symbol) and would
   need `add_message`/`Message` to accept `str | Role` to stay ergonomic at call sites. Which do
   you want?

## Suggested execution order (once questions are answered)

1. Scaffold `python/01_struct_skeleton/` (package dirs, `pyproject.toml`).
2. Use the same .venv folder as in previous port task
3. Copy `config.py` from `00_config`, remove `PROMPTS_DIR`; copy `tasks/base.py`/`tasks/player.py` unchanged.
4. Write `tool.py`, `message.py`, `context.py`.
5. Update `boukensha/__init__.py` to export `Config`, `Player`, `Tool`, `Message`, `Context`.
6. Port `examples/example.py`, run it against the existing `week1_baseline/.boukensha/settings.yaml`
   and compare output against `ruby/01_struct_skeleton/examples/example.rb`'s actual output
   (not just the README's stale sample) for parity.
7. Write `python/01_struct_skeleton/README.md` (design doc + porting-notes section, per the
   `00_config` precedent).
8. Add `bin/01_struct_skeleton_python`, consistent with the existing `bin/01_struct_skeleton_ruby`
   naming already in the repo — installing only shared deps into `python/.venv` per Q1's resolution.
9. If Q1 is resolved in favor of dropping per-step editable installs, retrofit
   `bin/00_config_python` (and its README) to match.
10. create executable bash script `01_struct_skeleton_python`in folder week1_baseline/bin to execute example.py
