# Plan: Port `ruby/09_global_executable` → `python/09_global_executable`

Status: **planned, not yet implemented**
Date: 2026-07-22

## Scope

1. Port the Ruby `09_global_executable` step into `week1_baseline/python/09_global_executable`.
2. Add two launcher scripts:
   - `week1_baseline/bin/09_global_executable_ruby`
   - `week1_baseline/bin/09_global_executable_python`

## Strategy

Copy `python/08_the_repl_loop` as the baseline, then apply the Ruby `08 → 09`
deltas. This step packages BOUKENSHA as a **global command**: a `boukensha`
executable plus a *loader* that resolves which step folder's library to run,
then boots the REPL. The library itself is unchanged except a version bump and a
few small reverts.

What step 09 adds/changes (from the Ruby `08 → 09` diff):
- New `bin/boukensha` — the executable entry point.
- New `lib/boukensha_loader.rb` — resolves which step to load
  (`BOUKENSHA_PATH` env → `~/.boukensharc` → bundled default), requires it,
  verifies it supports `repl`, then calls `Boukensha.repl`.
- New `boukensha.gemspec` — gem packaging (declares the executable).
- `version.rb`: `0.8.0` → `0.9.0`.
- **Reverts** of two step-08 additions:
  - `config.rb` `resolve_dir` drops the cwd `.boukensha` lookup (back to
    `BOUKENSHA_DIR` || `~/.boukensha`).
  - `client.rb` drops the special-case 401 message.
- `repl.rb` banner simplified: no API-key/dir-exists checks; shows plain
  `config` / `provider` / `model` lines.
- No `examples/` folder (the entry point is now `bin/boukensha`).

## Python packaging analog

Ruby's "install a gem so `boukensha` is on `$PATH`" maps to a Python
**console-script / executable**. The faithful, low-friction port keeps Ruby's
structure:
- a standalone **`boukensha_loader.py`** (a *top-level* module beside the
  `boukensha/` package — mirroring Ruby's `lib/boukensha_loader.rb` living
  outside `lib/boukensha/`, so it can import a *different* step's `boukensha`
  package),
- a **`bin/boukensha`** Python script (the executable),
- a `[project.scripts]` entry in `pyproject.toml` for the `pip install` path
  (the analog of the gemspec's `executables`).

"Loading a step" in Python = insert that step's directory (the one containing
its `boukensha/` package) onto `sys.path`, then `import boukensha`.

## New files

1. **`boukensha_loader.py`** (top level, next to `boukensha/`) — port of
   `lib/boukensha_loader.rb`:
   - `_BUNDLED_DIR = Path(__file__).resolve().parent` — this step's own folder,
     whose `boukensha/` package is the bundled default.
   - `resolve() -> Path`: returns the **step directory** containing a
     `boukensha/__init__.py`, resolved in order:
     1. `BOUKENSHA_PATH` env var → `Path(expanduser)`; error out (stderr +
        `sys.exit(1)`) with a helpful message if it has no `boukensha/__init__.py`.
     2. `~/.boukensharc` (a file with one path) → same validation.
     3. `_BUNDLED_DIR`.
   - `load_and_start_repl()`:
     - `step_dir = resolve()`; if `BOUKENSHA_DEBUG` env set, print
       `f"[boukensha] loading from: {step_dir}"`.
     - `sys.path.insert(0, str(step_dir))`; `import boukensha`.
     - if `not hasattr(boukensha, "repl")`: abort with the "does not support the
       interactive REPL (added in step 7)" guidance.
     - else `boukensha.repl()`.
   - `main()` → `load_and_start_repl()` (entry-point target).

2. **`bin/boukensha`** — Python executable (`#!/usr/bin/env python3`):
   ```python
   import sys
   from pathlib import Path
   sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # the step dir
   import boukensha_loader
   boukensha_loader.load_and_start_repl()
   ```
   `chmod +x`.

## Modified files (mirroring the Ruby `08 → 09` deltas)

3. **`boukensha/version.py`** — `VERSION = "0.9.0"`.

4. **`boukensha/config.py`** — revert `_resolve_dir()` to: `BOUKENSHA_DIR` if
   set, else `DEFAULT_DIR` (drop the cwd `./.boukensha` branch added in step 8).

5. **`boukensha/client.py`** — remove the `if response_status == 401: raise
   ApiError("authentication failed …")` block (back to the generic non-2xx error).

6. **`boukensha/repl.py`** — simplify `_banner()`: drop the API-key-status and
   `config_dir` existence logic; render plain lines:
   ```
     config:        {config_dir or "(default)"}
     provider:      {provider or "(default)"}
     model:         {model or "(default)"}
   ```
   (version padding unchanged; `VERSION` is now `0.9.0`).

7. **`boukensha/__init__.py`** — update the module docstring to Step 9 and the
   `repl` docstring wording (Ruby only tweaked a comment here). No behavior
   change. Keep all existing exports (`run`, `repl`, `Repl`, `VERSION`, …).

8. **Remove `examples/`** — mirror Ruby (step 9 has no examples; the entry point
   is `bin/boukensha`).

9. **`pyproject.toml`**:
   - `name = "boukensha"`, `version = "0.9.0"`,
     `description = "BOUKENSHA — global executable (Python port, Step 9)"`.
   - add `[project.scripts]` → `boukensha = "boukensha_loader:main"`.
   - include the top-level loader module in the build, e.g.
     `[tool.setuptools] py-modules = ["boukensha_loader"]` alongside the existing
     `packages.find` for `boukensha*`, so `pip install .` exposes the `boukensha`
     command (the pip analog of `gem install`).

10. **`README.md`** — rewrite as the Step 9 port doc: the loader resolution order
    (`BOUKENSHA_PATH` → `~/.boukensharc` → bundled), `BOUKENSHA_DEBUG`, running a
    specific step, and the pip-install path (`pip install .` → `boukensha` on
    `$PATH`). Note the Python specifics: "loading a step" = `sys.path` insertion +
    `import boukensha`; the loader is a standalone module (not inside the package)
    so it can load a *different* step's `boukensha`.

11. **`prompts/system.md`, `py.typed`** — carry forward unchanged (diff
    `system.md` 08→09 first; expected identical).

## bin scripts

12. **`bin/09_global_executable_ruby`** — the gem ships no dependencies, so avoid
    bundler: `cd .../ruby/09_global_executable && exec ruby bin/boukensha`
    (`bin/boukensha` already unshifts `lib` onto `$LOAD_PATH`).

13. **`bin/09_global_executable_python`** — shared-venv bootstrap (as the other
    `NN_*_python` launchers), then `exec .venv/bin/python 09_global_executable/bin/boukensha`.

Both scripts `chmod +x`.

## Verification

14. Byte-compile the package + loader
    (`python -m compileall python/09_global_executable`).
15. Offline loader unit checks (monkeypatch `sys.path` / env, no REPL start —
    call `resolve()` directly):
    - `BOUKENSHA_PATH` pointing at a valid step dir returns it; pointing at a dir
      with no `boukensha/__init__.py` exits non-zero with the guidance message.
    - `~/.boukensharc` (temp HOME) with a valid path is used when `BOUKENSHA_PATH`
      is unset; a bad path in it exits with guidance.
    - with neither set, `resolve()` returns `_BUNDLED_DIR` (this step's folder).
16. Offline `load_and_start_repl` check: monkeypatch `boukensha.repl` to a no-op
    (or point `BOUKENSHA_PATH` at this step and feed EOF on stdin) and assert it
    resolves, imports `boukensha`, and calls `repl`; and that a stubbed step
    module lacking `repl` triggers the abort path.
17. Reverted-behavior checks: `_resolve_dir` ignores `./.boukensha` (only
    `BOUKENSHA_DIR`/default); `client` no longer special-cases 401; the banner has
    no "API key" line and includes a `model:` line.
18. Live smoke (needs Ollama + `.boukensha`): pipe `"hi\n/exit\n"` into
    `bin/09_global_executable_python`; confirm the banner (v0.9.0, config/provider/
    model lines), a reply, and a session `*.jsonl`. Also verify
    `BOUKENSHA_DEBUG=1` prints the `[boukensha] loading from: …` line, and
    `BOUKENSHA_PATH=<abs>/python/07_the_run_dsl` loads step 7's package instead.
    Compare against `bin/09_global_executable_ruby`.
