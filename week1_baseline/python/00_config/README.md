# 00 · Configuration (Python port)

Python 3 port of [`ruby/00_config`](../../ruby/00_config/README.md). Same design, same
`.boukensha/` directory contract, same config schema — see the Ruby README for the full design
rationale. This document covers the Python-specific implementation and how it differs from the
Ruby source.

We want to be able to manage all configuration from an external file, e.g. `~/.boukensha/settings.yaml`.
We want a dedicated class to handle configuration: `boukensha.config.Config`. As configuration
grows across later iterations, this schema and class will keep being extended. Defaults can be
hardcoded; configurable values must not be.

Configuration is organised by **task** — a role in the agentic loop bound to its own LLM.
week1_baseline only drives a single `player` task (the main loop), but a more advanced loop will
assign different LLMs to different tasks. A task is either a "single-task" or a "multi-task" —
the latter being a full agent.

## Design considerations

We want to lean on the standard library as much as possible. Two runtime dependencies are
unavoidable for a faithful port:

- **`python-dotenv`** — Python equivalent of the Ruby `dotenv` gem, for loading `.env`.
- **`PyYAML`** — Ruby's `YAML` module is stdlib; Python has no stdlib YAML parser, so this is a
  dependency the Ruby side didn't need. It's the only way to keep `settings.yaml` as the shared
  config format between the Ruby and Python implementations.

Everything else (path resolution, file I/O) uses the standard library (`pathlib`, `os`).

## Code layout

| File | Purpose |
|------|---------|
| `boukensha/config.py` | `Config` class — port of `lib/boukensha/config.rb` |
| `boukensha/tasks/base.py` | Abstract `Base` task (provider/model + prompt resolution) — port of `lib/boukensha/tasks/base.rb` |
| `boukensha/tasks/player.py` | Concrete `Player` task (the main loop) — port of `lib/boukensha/tasks/player.rb` |
| `boukensha/__init__.py` | Top-level package exports — port of `lib/boukensha.rb` |
| `prompts/system.md` | Default system prompt shipped with the package (copied verbatim from the Ruby side) |
| `examples/example.py` | Runnable smoke test — port of `examples/example.rb` |
| `pyproject.toml` | Package metadata + the two runtime dependencies above |

Package layout mirrors the Ruby `lib/boukensha/` tree directly (flat, not a `src/` layout) so the
file-for-file mapping to the Ruby source stays obvious.

## Config directory resolution

Identical to the Ruby side. `Config` looks for a `.boukensha/` directory in this order:

1. **`BOUKENSHA_DIR` env var** — set this to point at any directory you like.
2. **`~/.boukensha`** — the default location for a real install (`pathlib.Path.home()`).

## Config directory structure

```
.boukensha/
  .env                 # stores credentials eg. LLM APIs (never committed to repo)
  settings.yaml        # all non-secret settings
  prompts/
    <task>/
      system.md        # per-task override for the default system prompt (optional)
```

## Tasks

`boukensha.tasks.base.Base` is an abstract stateless class. All behaviour is expressed as
`@classmethod`s that accept a task's settings `dict` — no instances are ever created. Concrete
subclasses override `task_name()`. For now only `boukensha.tasks.player.Player` exists; future
steps add per-turn ceilings (`max_iterations`, `max_turn_tokens`, `max_output_tokens`,
`compaction_threshold`) — these are **not** read yet.

`Config.tasks()` returns the raw dict from `settings.yaml` under `tasks:`. Pass a name to look up
a specific task's settings dict, then pass it to the stateless class:

```python
from boukensha.config import Config, PROMPTS_DIR
from boukensha.tasks.player import Player

config = Config()
player_settings = config.tasks("player")

Player.provider(player_settings)
Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=PROMPTS_DIR,
)
```

## System prompt resolution

Per task, `Player.system_prompt` is resolved in this order:

1. **`.boukensha/prompts/<task>/system.md`** — used when the task's `prompt_override.system` is
   `true` and the file exists.
2. **`prompts/system.md`** — the default system prompt shipped with the package.

## Configuration schema

Same schema as the Ruby side — `tasks` (map of task name → task config: provider, model,
prompt_override) and `mud` (MUD connection info):

```yaml
tasks:
  player:
    provider: anthropic        # provider name (string)
    model: claude-haiku-4-5
    prompt_override:
      system: true
mud:
  host: localhost
  port: 4000
  username: dummy
  password: helloworld
```

## Porting notes (deviations from the Ruby source)

- **Symbol/string dual-key lookups collapse to plain string keys.** Ruby's `dig`/`fetch` check
  both `node[key.to_s]` and `node[key.to_sym]` because Ruby hash/YAML keys can be either.
  `yaml.safe_load` always produces plain `str` keys in Python, so `Config.dig` and
  `Base._fetch` only need a single string-keyed lookup.
- **`prompt_override?` → `prompt_override`.** A trailing `?` isn't valid in a Python identifier.
- **`Config#to_s`/`#inspect` → `Config.__repr__`**, same `#<Boukensha.Config dir=... tasks=...>`
  shape.
- **Ruby's `Boukensha::Tasks::Player` nested-class naming → `boukensha.tasks.player.Player`.**
  The Python module path already does the namespacing; there's no need to also prefix the class
  name.
- **`dir` is a `pathlib.Path`, not a string** (Ruby stores it as a `String`). Idiomatic Python
  favors `Path` objects for filesystem paths; it's converted to text only for display
  (`__repr__`, f-strings).
- **`task_name` stayed a classmethod (`task_name()`), not a class attribute**, so an
  un-overridden subclass raises `NotImplementedError` immediately (mirroring Ruby's
  `raise NotImplementedError`) instead of failing later with an `AttributeError` on first use.
- **No `abc.ABC`/`@abstractmethod`.** `Base.task_name()` raises `NotImplementedError` directly,
  the same mechanism the Ruby source uses (`raise NotImplementedError`) — keeps the port
  1:1 rather than introducing extra machinery.
- **Full type hints throughout** (`dict[str, Any]`, `Path | None`, etc.) plus a `py.typed`
  marker, since Ruby has no equivalent static-typing convention to port from.

## Setup

Requires Python ≥ 3.11. One venv lives at `python/.venv`, shared across every `python/NN_*`
step — but only for the third-party runtime deps (`python-dotenv`, `PyYAML`). **No step's own
`boukensha` package is `pip install`-ed into it.** Every step ships its own top-level `boukensha`
package (this step's, `01_struct_skeleton`'s, etc.) — `pip install -e`-ing more than one of them
into the same venv would collide on that shared import name, with whichever was installed last
silently shadowing the others. Instead, each step's `examples/example.py` adds its own package
directory to the front of `sys.path` at runtime, mirroring how the Ruby examples
`require_relative "../lib/boukensha"` from within their own step folder — only one step's code
is ever "active" per process, exactly like the Ruby side.

```bash
cd week1_baseline/python
python3 -m venv .venv
source .venv/bin/activate
pip install "python-dotenv>=1.0" "PyYAML>=6.0"
```

## Run example

```bash
./week1_baseline/bin/00_config_python
```

This bootstraps `python/.venv` on first run (creating it and installing the shared runtime deps)
and is safe to re-run any time. Or, with the shared venv active:

```bash
python 00_config/examples/example.py
```

`examples/example.py` adds this package's directory to `sys.path` itself (see above), so it runs
standalone as long as `python-dotenv` and `PyYAML` are importable — no install of this package
required or supported.

Expected output (values from your `.boukensha/`):

```
=== Boukensha Step 0: Configuration ===

Config dir:     /home/andrew/Sites/Claude-Code-Camp/.boukensha
Tasks:          player

-- player task --
Provider:       anthropic
Model:          claude-haiku-4-5
Prompt override?True
System prompt:  You are a MUD player assistant. Use the tools available to y...

MUD host:       localhost:4000
MUD user:       dummy

API key set?    true

#<Boukensha.Config dir=/home/andrew/Sites/Claude-Code-Camp/.boukensha tasks=player>
```
