# 02 · The Tool Registry (Python port)

Python 3 port of [`ruby/02_the_registry`](../../ruby/02_the_registry/README.md). Same design —
see the Ruby README for the full narrative and expected-output sample. This document covers the
Python-specific implementation and how it differs from the Ruby source.

The Tool Registry is how Boukensha manages what capabilities the agent can use. It has two jobs:

1. storing tools
2. dispatching tools when asked

The agent never calls a tool directly. It emits a structured request (name + args) and the
`Registry` looks up the tool and runs it.

## New files (vs. step 1)

| File | Purpose |
|---|---|
| `boukensha/registry.py` | The `Registry` class — registers tools and dispatches calls |
| `boukensha/errors.py` | `UnknownToolError` |

Everything else (`config.py`, `tool.py`, `message.py`, `context.py`, `tasks/base.py`,
`tasks/player.py`) is an unchanged carry-forward from `01_struct_skeleton` — the Ruby sources for
those files are byte-identical between the two steps.

## `boukensha.registry.Registry`

| Method | Description |
|---|---|
| `Registry(context)` | Wraps a `Context`; registered tools attach to it |
| `tool(name, *, description, parameters=None)` | Decorator — registers the decorated function as a tool on the context, returns the function unchanged |
| `dispatch(name, args=None)` | Looks up a tool by name and calls it with the provided args |

`Registry` is a thin façade in front of `Context` — `Context.register_tool` still exists and
still does the actual storing; `Registry.tool` just builds the `Tool` and calls it for you.

## `boukensha.errors.UnknownToolError`

Raised when `dispatch` is called with a name that has no registered tool. A harness needs
explicit error boundaries — an unrecognised tool name should never silently fail.

```
UnknownToolError: No tool registered as 'flee'
```

## Code layout

| File | Purpose |
|------|---------|
| `boukensha/config.py` | `Config` class — unchanged copy from `01_struct_skeleton` |
| `boukensha/tool.py` | `Tool` dataclass — unchanged copy from `01_struct_skeleton` |
| `boukensha/message.py` | `Message` dataclass — unchanged copy from `01_struct_skeleton` |
| `boukensha/context.py` | `Context` class — unchanged copy from `01_struct_skeleton` |
| `boukensha/tasks/base.py` | Abstract `Base` task — unchanged copy from `01_struct_skeleton` |
| `boukensha/tasks/player.py` | Concrete `Player` task — unchanged copy from `01_struct_skeleton` |
| `boukensha/registry.py` | `Registry` class — port of `lib/boukensha/registry.rb` |
| `boukensha/errors.py` | `UnknownToolError` — port of `lib/boukensha/errors.rb` |
| `boukensha/__init__.py` | Top-level package exports — port of `lib/boukensha.rb` |
| `examples/example.py` | Runnable smoke test — port of `examples/example.rb` |
| `pyproject.toml` | Package metadata + the two runtime dependencies (`python-dotenv`, `PyYAML`) |

No `prompts/` directory in this step (unchanged from step 1).

## Porting notes (deviations from the Ruby source)

Carries forward every convention already established in
[`python/00_config`'s README](../00_config/README.md#porting-notes-deviations-from-the-ruby-source)
and [`python/01_struct_skeleton`'s README](../01_struct_skeleton/README.md#porting-notes-deviations-from-the-ruby-source)
— not repeated here. New for this step:

- **Ruby's block-taking `Registry#tool` → a Python decorator.** Ruby's DSL —
  `registry.tool("move", description: ..., parameters: {...}) { |direction:| ... }` — is a
  method call with a trailing block. The idiomatic Python shape for "metadata up front, function
  body after" is a decorator factory:

  ```python
  @registry.tool(
      "move",
      description="Move the player in a direction (north, south, east, west, up, down)",
      parameters={"direction": {"type": "string"}},
  )
  def move(direction: str) -> str:
      return f"You move {direction} into a torch-lit corridor."
  ```

  `Registry.tool(name, *, description, parameters=None)` returns an inner decorator that builds
  the `Tool`, registers it on the context, and returns the original function unchanged (so the
  name stays directly callable/testable outside the registry too — normal decorator etiquette).
  This is a deliberate deviation from a line-for-line port (a plain method taking the callable as
  an argument would be closer to Ruby) in favor of the more idiomatic Python shape for this exact
  "block-taking DSL method" pattern.
- **`dispatch`'s string/symbol key translation doesn't port at all.** Ruby's `dispatch` calls
  `args.transform_keys(&:to_sym)` before invoking the block, because Ruby blocks with keyword
  args need symbol keys while dispatched args arrive as string keys (mimicking a JSON API
  payload) — this is the whole subject of the Ruby README's "Considerations" section. Python's
  `**kwargs` already requires and accepts string keys, so `Registry.dispatch` is a direct
  `tool.block(**(args or {}))` with no translation step. The gotcha the Ruby side calls out
  simply isn't present in Python.
- **`Registry.dispatch(name, args=None)`** — `args` defaults to `None` rather than a mutable
  `{}` (standard Python practice for a dict default), treated as empty when omitted.
- **`UnknownToolError(Exception)`** — a bare one-liner, same as Ruby's
  `UnknownToolError < StandardError`. No shared `BoukenshaError` base class, since Ruby doesn't
  have one either and there's only the one exception type to port.
- **`Registry._context`** — underscore-prefixed by convention (Python has no true privacy);
  matches that Ruby's `@context` is never exposed via `attr_reader`.

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
./week1_baseline/bin/02_the_registry_python
```

This bootstraps `python/.venv` on first run and is safe to re-run any time. Or, with the shared
venv active:

```bash
python 02_the_registry/examples/example.py
```

Expected output (values from your `.boukensha/`):

```
=== BOUKENSHA Step 2: Tool Registry ===

Config:  #<Boukensha.Config dir=/home/andrew/Sites/Claude-Code-Camp/.boukensha tasks=player>
Context: #<Context task=player turns=0 tools=2>
Tools:
  #<Tool name=move description=Move the player in a direction (north, so params=['direction']>
  #<Tool name=shout description=Shout a message so everyone in the zone c params=['message']>

Dispatching 'shout' with message='dragon spotted'...
Result: DRAGON SPOTTED

Dispatching 'move' with direction='north'...
Result: You move north into a torch-lit corridor.

UnknownToolError caught: No tool registered as 'flee'
```
