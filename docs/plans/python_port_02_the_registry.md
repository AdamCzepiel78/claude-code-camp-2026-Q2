# Plan: Port `ruby/02_the_registry` to Python

## Goal

Port `week1_baseline/ruby/02_the_registry` into `week1_baseline/python/02_the_registry/`
(directory doesn't exist yet). This step adds the **Tool Registry** — a `Registry` class that
owns tool registration and dispatch on top of the `Tool`/`Message`/`Context` structs already
ported in `01_struct_skeleton` — plus a dedicated `UnknownToolError`. It carries forward the
package layout, naming, and porting conventions established in `00_config` and
`01_struct_skeleton` (see `docs/plans/python_port_00_config.md`,
`docs/plans/python_port_01_struct_skeleton.md`, and `python/00_config/README.md`'s "Porting
notes" section) — this plan only calls out what's new or different for step 2.

## Reference files (what to port from)

| Ruby file                                                             | Role                                                                                                                                                                                                   |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `week1_baseline/ruby/02_the_registry/README.md`                     | Spec for this step — Registry API table, dispatch flow,`UnknownToolError`, expected output                                                                                                          |
| `week1_baseline/ruby/02_the_registry/lib/boukensha/errors.rb`       | `Boukensha::UnknownToolError < StandardError` — one-line error class                                                                                                                                |
| `week1_baseline/ruby/02_the_registry/lib/boukensha/registry.rb`     | `Registry` class: `initialize(context)`, `tool(name, description:, parameters:, &block)`, `dispatch(name, args)`                                                                               |
| `week1_baseline/ruby/02_the_registry/lib/boukensha/tool.rb`         | **Byte-identical** to step 1's `tool.rb`                                                                                                                                                       |
| `week1_baseline/ruby/02_the_registry/lib/boukensha/message.rb`      | **Byte-identical** to step 1's `message.rb`                                                                                                                                                    |
| `week1_baseline/ruby/02_the_registry/lib/boukensha/context.rb`      | **Byte-identical** to step 1's `context.rb`                                                                                                                                                    |
| `week1_baseline/ruby/02_the_registry/lib/boukensha/config.rb`       | **Byte-identical** to step 1's `config.rb`                                                                                                                                                     |
| `week1_baseline/ruby/02_the_registry/lib/boukensha/tasks/base.rb`   | **Byte-identical** to step 0/1's `tasks/base.rb`                                                                                                                                               |
| `week1_baseline/ruby/02_the_registry/lib/boukensha/tasks/player.rb` | **Byte-identical** to step 0/1's `tasks/player.rb`                                                                                                                                             |
| `week1_baseline/ruby/02_the_registry/lib/boukensha.rb`              | Top-level require wiring (adds`errors`, `registry` requires)                                                                                                                                       |
| `week1_baseline/ruby/02_the_registry/examples/example.rb`           | Runnable smoke test — builds`Context` + `Registry`, registers `move`/`shout` tools via the registry, dispatches both plus an unknown tool to demonstrate `UnknownToolError`                 |
| `week1_baseline/ruby/02_the_registry/Gemfile`                       | Unchanged from steps 0/1 (`dotenv` only)                                                                                                                                                             |
| `week1_baseline/python/01_struct_skeleton/` (already-ported step 1) | Source for files that carry forward unchanged:`config.py`, `tool.py`, `message.py`, `context.py`, `tasks/base.py`, `tasks/player.py`, plus established package/README/launcher conventions |

## What's different from step 1 (read before porting)

- **Only two new files land in `lib/`: `errors.rb` and `registry.rb`.** Diffing
  `ruby/01_struct_skeleton/lib/boukensha/` against `ruby/02_the_registry/lib/boukensha/` shows
  `config.rb`, `tool.rb`, `message.rb`, `context.rb`, `tasks/base.rb`, `tasks/player.rb` are all
  untouched. The Python `config.py`, `tool.py`, `message.py`, `context.py`,
  `tasks/base.py`, `tasks/player.py` already ported for `01_struct_skeleton` can be copied
  forward as-is.
- **Tool registration moves off `Context` and onto `Registry`.** `Context.register_tool` still
  exists (step 1 behavior, unchanged) but the example no longer calls it directly — it goes
  through `Registry#tool`, which builds the `Tool` and calls `context.register_tool(tool)`
  internally. `Registry` is a thin façade in front of `Context`, not a replacement for it.
- **Ruby's `Registry#tool` takes a block (`&block`)**; there is no direct Python equivalent
  syntax. See "Porting decisions" below for the chosen approach (decorator-based).
- **`Registry#dispatch` does a Ruby-specific string→symbol key conversion**
  (`args.transform_keys(&:to_sym)`) before calling the block with `**kwargs`, because Ruby
  blocks with keyword args need symbol keys but dispatched args arrive as string keys (mimicking
  a JSON API payload). **This entire concern doesn't exist in Python** — Python's `**kwargs`
  already requires (and accepts) string keys, so `dispatch` is a straight `tool.block(**args)`
  with no key translation step. Flag this explicitly in the Python README's porting notes,
  since the Ruby README's whole "Considerations" section is about a gotcha that simply isn't
  present on the Python side.
- **`UnknownToolError`** — Ruby defines it as `Boukensha::UnknownToolError < StandardError`, a
  bare one-liner with no custom `initialize`/message formatting (the message is passed at
  `raise` call sites: `raise UnknownToolError, "No tool registered as '#{name}'"`). Port as a
  bare `class UnknownToolError(Exception): pass`, message formatted at the `raise` call site in
  `registry.py`, same as Ruby — no need for a shared `BoukenshaError` base class since Ruby
  doesn't have one either (would be scope creep for a single exception type).

## Target layout

```
week1_baseline/python/02_the_registry/
  boukensha/
    __init__.py          # exports Config, Player, Tool, Message, Context, Registry, UnknownToolError
    config.py             # unchanged copy from 01_struct_skeleton
    tool.py                # unchanged copy from 01_struct_skeleton
    message.py             # unchanged copy from 01_struct_skeleton
    context.py             # unchanged copy from 01_struct_skeleton
    errors.py               # new — UnknownToolError
    registry.py              # new — Registry
    tasks/
      __init__.py
      base.py               # unchanged copy from 01_struct_skeleton
      player.py             # unchanged copy from 01_struct_skeleton
  examples/
    example.py             # from examples/example.rb
  README.md                 # adapted from ruby README + "porting notes" section (per established precedent)
  pyproject.toml
```

No `prompts/` directory in this step (unchanged from step 1).

## Porting decisions (new for this step)

- **`Registry#tool`'s block → Python decorator.** Ruby's DSL —
  `registry.tool("move", description: ..., parameters: {...}) { |direction:| ... }` — is a
  method that takes a name/kwargs and a trailing block. The idiomatic Python shape for "a call
  that takes metadata up front and a function body after" is a decorator factory:

  ```python
  @registry.tool(
      "move",
      description="Move the player in a direction (north, south, east, west, up, down)",
      parameters={"direction": {"type": "string"}},
  )
  def move(direction: str) -> str:
      return f"You move {direction} into a torch-lit corridor."
  ```

  `Registry.tool(name, *, description, parameters=None)` returns an inner `register(func)`
  decorator that builds a `Tool(name, description, parameters or {}, func)`, calls
  `self._context.register_tool(tool)`, and returns `func` unchanged (so the decorated name stays
  callable/testable on its own, matching normal decorator etiquette). This is a real deviation
  from a literal 1:1 port (a plain method call with a lambda/positional-callable argument would
  be closer line-for-line to Ruby), but it's the more "professional Python" shape for this exact
  pattern — flagged as an open question below in case a closer literal port is preferred instead.
- **`Registry.dispatch(name, args=None)`** — `args: dict[str, Any] | None = None` (avoiding a
  mutable default), treated as `{}` when `None`; looks up `context.tools.get(name)`, raises
  `UnknownToolError(f"No tool registered as '{name}'")` when missing, otherwise returns
  `tool.block(**args)`. No key-casing translation (see above).
- **`Registry` holds a `Context` reference** (`self._context = context`, private/underscore-
  prefixed per Python convention for "not part of the public API" — Ruby's `@context` is
  private by default via `attr_reader` omission, so this matches intent even though Python has
  no true privacy).
- **`errors.py` stays a one-class module**, mirroring Ruby's `errors.rb` — no speculative base
  exception class (see above).

## Open questions

1. **Decorator-based `Registry.tool` vs. a closer literal port.** Recommendation is the
   decorator shown above (idiomatic, and it's what "follow Python best practices" points
   toward for a block-taking DSL method). The closer-to-Ruby alternative is a plain method
   taking the callable positionally or as a keyword, e.g.
   `registry.tool("move", description=..., parameters=..., block=lambda direction: ...)`,
   which is a more mechanical 1:1 port (also consistent with how `01_struct_skeleton`'s
   `example.py` already constructs a bare `Tool(...)` with a positional `lambda`). Which do you
   want — decorator (recommended) or plain callable argument?
2. **`Registry.tool`'s return value.** Ruby's `tool` method returns the built `Tool` (implicit
   last-expression return). If we go with the decorator approach from Q1, the decorator itself
   returns the original `func` (so the name stays usable), not the `Tool` — matching normal
   Python decorator conventions rather than Ruby's return value 1:1. Confirm that's fine, or
   would you rather the decorator return the `Tool` instance instead of `func` (at the cost of
   the decorated name no longer being directly callable outside the registry)?

## Suggested execution order (once questions are answered)

1. Scaffold `python/02_the_registry/` (package dirs, `pyproject.toml`), using the same shared
   `python/.venv` convention as prior steps (no per-step editable install).
2. Copy `config.py`, `tool.py`, `message.py`, `context.py`, `tasks/base.py`, `tasks/player.py`
   unchanged from `01_struct_skeleton`.
3. Write `errors.py` (`UnknownToolError`) and `registry.py` (`Registry`, per the answered
   open questions above).
4. Update `boukensha/__init__.py` to export `Config`, `Player`, `Tool`, `Message`, `Context`,
   `Registry`, `UnknownToolError`.
5. Port `examples/example.py`: build `Context`, wrap it in a `Registry`, register `move` and
   `shout`, print `Config`/`Context`/tool list, dispatch `shout` then `move`, then dispatch an
   unregistered `"flee"` tool and catch/print `UnknownToolError` — run it against the existing
   `week1_baseline/.boukensha/settings.yaml` and compare output against
   `ruby/02_the_registry/examples/example.rb`'s actual output for parity.
6. Write `python/02_the_registry/README.md` (design doc + porting-notes section, including the
   dispatch key-casing note above), per the `00_config`/`01_struct_skeleton` precedent.
7. Add `bin/02_the_registry_python`, consistent with `bin/01_struct_skeleton_python` and the
   existing `bin/02_the_registry_ruby` naming already in the repo — installing only the shared
   deps into `python/.venv`.
