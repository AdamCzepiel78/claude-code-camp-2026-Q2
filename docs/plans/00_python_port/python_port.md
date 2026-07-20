# Plan: Port `ruby/00_config` to Python

## Goal

Port the `Boukensha::Config` step (`week1_baseline/ruby/00_config`) to Python 3, landing it in
the already-created (currently empty) `week1_baseline/python/00_config/` directory. This is the
first of the numbered `ruby/NN_*` steps to be ported and will set the pattern (package layout,
dependency management, naming conventions) that later steps (`01_struct_skeleton` through
`12_context`) are expected to follow.

## Reference files (what to port from)

Read these before writing any Python — they are the full source of truth for step 0:

| Ruby file | Role |
|---|---|
| `week1_baseline/ruby/00_config/README.md` | Spec/design doc for this step — directory resolution, config schema, task model, prompt resolution order, expected CLI output |
| `week1_baseline/ruby/00_config/lib/boukensha/config.rb` | `Boukensha::Config` — dir resolution, `.env` loading, `settings.yaml` loading, `tasks`, `mud_*`, `dig` |
| `week1_baseline/ruby/00_config/lib/boukensha/tasks/base.rb` | Abstract stateless `Tasks::Base` — `provider`, `model`, `prompt_override?`, `prompt`/`system_prompt` resolution |
| `week1_baseline/ruby/00_config/lib/boukensha/tasks/player.rb` | Concrete `Tasks::Player < Base`, just sets `task_name = "player"` |
| `week1_baseline/ruby/00_config/lib/boukensha.rb` | Top-level require wiring (→ Python package `__init__.py`) |
| `week1_baseline/ruby/00_config/prompts/system.md` | Default system prompt shipped with the library — copy as-is |
| `week1_baseline/ruby/00_config/examples/example.rb` | Runnable smoke test — Python equivalent must reproduce the same output shape |
| `week1_baseline/ruby/00_config/Gemfile` | Only dependency is `dotenv` — Python equivalent dependency list |
| `week1_baseline/.boukensha/settings.yaml` | Live example config on this machine — useful for manually verifying the port's output matches the Ruby example's documented output in the README |
| `week1_baseline/bin/00_config` | Existing bash launcher for the Ruby example (`bundle exec ruby examples/example.rb`) — for context only, not being changed by this plan unless you want it extended (see open questions) |
| `week1_baseline/ruby/ITERATIONS.md` (step "0 Configuration" + porting notes near "we can and will port the code over to Python") | Background on why this exists and constraints carried across the whole port effort |

## Target layout

```
week1_baseline/python/00_config/
  boukensha/
    __init__.py          # from lib/boukensha.rb
    config.py             # from lib/boukensha/config.rb
    tasks/
      __init__.py
      base.py              # from lib/boukensha/tasks/base.rb
      player.py            # from lib/boukensha/tasks/player.rb
  prompts/
    system.md              # copied verbatim from ruby/00_config/prompts/system.md
  examples/
    example.py             # from examples/example.rb
  README.md                 # adapted from ruby README, Python-flavored run instructions
  requirements.txt (or pyproject.toml — see open questions)
```

## Porting notes (Ruby → Python translation decisions)

- **Config dir resolution**: `BOUKENSHA_DIR` env var → `Path.home() / ".boukensha"` default, via `pathlib.Path`, mirroring `Config::DEFAULT_DIR` / `resolve_dir`.
- **`.env` loading**: use `python-dotenv`'s `load_dotenv()`, the direct Python equivalent of the Ruby `dotenv` gem — same non-stdlib exception the Ruby README already carves out.
- **`settings.yaml` loading**: Ruby's `YAML.safe_load` is stdlib; Python's `yaml` (PyYAML) is **not** stdlib. This is a deviation from the "stdlib only" principle that the Ruby side didn't have to make — flagged in open questions below.
- **Symbol/string dual-key lookups**: Ruby's `dig`/`fetch` check both `node[key.to_s]` and `node[key.to_sym]` because Ruby YAML/hash keys can be either. Python's `yaml.safe_load` always produces plain `str` keys, so the Python `dig`/task `fetch` helpers can simplify to single string-keyed lookups — no dual lookup needed. This is a simplification, not a straight line-for-line port.
- **`Tasks::Base` "abstract stateless class, all class methods"**: Ruby models this with `def self.foo`. Python equivalent: `@classmethod`/`@staticmethod` methods on `Base`, with `task_name` raising `NotImplementedError` (mirroring the Ruby raise) rather than introducing `abc.ABC` machinery — keeps it a direct, simple port. `Player` overrides `task_name`.
- **Ruby `?`-suffixed method** `prompt_override?` isn't valid Python syntax — port as `prompt_override` (drop the `?`), or `is_prompt_override` if we want to avoid clashing with the returned-bool-ness being ambiguous. Proposing `prompt_override`.
- **`Config#to_s`/`#inspect`** → Python `__str__`/`__repr__` on `Config`, same format: `<Boukensha::Config dir=... tasks=...>` (or `Boukensha.Config` — see open questions on naming).
- **`prompts/system.md`** copied byte-for-byte; default/user prompt resolution order (per-task override → shipped default) ports directly, using `Path.read_text().strip()` in place of `File.read(path).strip`.
- **`examples/example.py`** should print the same fields as `example.rb` (config dir, task list, provider/model/prompt-override/system-prompt-preview for `player`, MUD host/user, whether `ANTHROPIC_API_KEY` is set, and the `repr(config)` line) so the two can be run side-by-side against the same `.boukensha/` and diffed for parity.

## Open questions

1. **PyYAML dependency** — Ruby's `YAML` is stdlib, so the Ruby README's "stdlib as much as possible, only add dotenv" rule holds cleanly. Python has no stdlib YAML parser, so a straight port needs `pyyaml` in addition to `python-dotenv`. OK to add `pyyaml`, or would you rather the Python side use a `settings.json` /stdlib `tomllib` (Python 3.11+ stdlib) instead of YAML to stay dependency-minimal? (Would diverge the config file format from the Ruby side.)
2. **Dependency management convention** — the repo has precedent for both `requirements.txt` (e.g. `week0_explore/explore_architecture/03b_subagent_sdk`) and `pyproject.toml` (`week0_explore/circlemud-world-parser`). Since this port sets the pattern for every later step, which do you want: plain `requirements.txt` + venv, or `pyproject.toml`? Any minimum Python version to target (system default here is 3.12)?
3. **Package granularity across steps** — should each numbered python step (`00_config`, `01_struct_skeleton`, …) be a fully self-contained package with its own `requirements.txt`/venv like the Ruby gems are, or should there be one shared `boukensha` package under `python/` that all steps import from (with step folders holding only the delta/examples for that step)? This affects how `01_struct_skeleton` onward will be structured, so worth deciding now rather than after step 0 is already committed to one layout.
4. **`bin/00_config` launcher** — the existing `week1_baseline/bin/00_config` only runs the Ruby example. Do you want a parallel `bin/00_config_python` (or similar) added in this pass, or is running `python3 examples/example.py` directly from `python/00_config/` sufficient for now?
5. **Naming style** — OK with `Boukensha::Config` → plain `boukensha.config.Config` (module path does the namespacing, no nested class prefix), and `Boukensha::Tasks::Player` → `boukensha.tasks.player.Player`? This is the idiomatic Python mapping but is a structural (not just syntactic) departure from the Ruby module nesting.

## Suggested execution order (once questions are answered)

1. Scaffold `python/00_config/` package skeleton + chosen dependency file.
2. Port `Config` (`config.py`) — dir resolution, `.env`/`settings.yaml` loading, `tasks`, `mud_*`, `dig`, `__str__`.
3. Port `Tasks::Base` (`tasks/base.py`) and `Tasks::Player` (`tasks/player.py`).
4. Copy `prompts/system.md`.
5. Port `examples/example.py`, run it against the existing `week1_baseline/.boukensha/settings.yaml` and compare output against the Ruby example's documented output in `ruby/00_config/README.md` for parity.
6. Write/adapt `python/00_config/README.md`.
7. (If confirmed in Q4) add a bin launcher.
