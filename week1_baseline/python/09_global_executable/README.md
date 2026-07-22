# 09 · Global Executable (Python port)

Python 3 port of [`ruby/09_global_executable`](../../ruby/09_global_executable/README.md). Same
design — see the Ruby README for the full considerations. This document covers the Python-specific
implementation.

This step packages BOUKENSHA as a **global `boukensha` command**. The library itself is unchanged
(a version bump + a couple of small reverts); what's new is a *loader* that resolves which step
folder to run and boots the REPL.

## What this step adds

| File | Purpose |
|---|---|
| `bin/boukensha` | The executable — makes the loader importable and hands off to it |
| `boukensha_loader.py` | Standalone module: resolves *which step* to load, then starts the REPL |
| `pyproject.toml` `[project.scripts]` | `pip install .` → `boukensha` on `$PATH` (the pip analog of the gem) |

The loader is a **top-level module, deliberately outside the `boukensha/` package** — mirroring
Ruby's `lib/boukensha_loader.rb` sitting outside `lib/boukensha/` — so it can import a *different*
step's `boukensha` package by name.

## How a step is chosen

The loader resolves in this order:

| Priority | Source | Example |
|---|---|---|
| 1 | `BOUKENSHA_PATH` env var | `BOUKENSHA_PATH=~/…/python/07_the_run_dsl boukensha` |
| 2 | `~/.boukensharc` file | `echo ~/…/python/08_the_repl_loop > ~/.boukensharc` |
| 3 | Bundled default | just run `boukensha` (this step's own package) |

`BOUKENSHA_PATH` must point to a step folder that contains a `boukensha/__init__.py`. **"Loading a
step"** in Python = insert that directory onto `sys.path`, then `import boukensha`.

The config directory (`settings.yaml`, `.env`, `system.md`) is separate — controlled by
`BOUKENSHA_DIR` (default `~/.boukensha`).

## Running

```bash
bin/09_global_executable_python                     # from week1_baseline/ — bundled default
BOUKENSHA_DEBUG=1 bin/09_global_executable_python   # prints "[boukensha] loading from: …"
```

Or install it so `boukensha` works from anywhere:

```bash
cd week1_baseline/python/09_global_executable
pip install .        # exposes the `boukensha` console script
boukensha            # runs the bundled step's REPL
BOUKENSHA_PATH=$PWD/../07_the_run_dsl boukensha   # run step 7 instead
```

A step older than the REPL (before step 7) has no `repl`, so the loader aborts with guidance to
point `BOUKENSHA_PATH` at step 7 or later.

## Changes from step 8

- `VERSION` → `0.9.0`.
- `Config._resolve_dir` reverts to `BOUKENSHA_DIR` || `~/.boukensha` (drops the step-8 cwd lookup).
- `Client` no longer special-cases HTTP 401.
- The REPL banner is simplified: no API-key/dir-exists checks; plain `config` / `provider` /
  `model` lines.
- No `examples/` — the entry point is now `bin/boukensha`.
