"""Port of ``lib/boukensha_loader.rb``.

Resolves which step folder to load the ``boukensha`` package from, then boots the
REPL. Kept as a *standalone* top-level module (not inside the ``boukensha``
package) so it can import a *different* step's ``boukensha`` package by name —
mirroring Ruby's ``lib/boukensha_loader.rb`` living outside ``lib/boukensha/``.

Resolution order:
  1. BOUKENSHA_PATH environment variable (selects which *step* dir to load)
  2. ~/.boukensharc  (a file containing a single path)
  3. The step directory this loader ships in (the bundled default)

"Loading a step" means: insert that step's directory (the one containing its
``boukensha/`` package) onto ``sys.path``, then ``import boukensha``.

The config directory (settings.yaml, .env, system.md) is separate — controlled by
BOUKENSHA_DIR (default ~/.boukensha).

Examples:
  boukensha                                                    # bundled lib + ~/.boukensha
  BOUKENSHA_PATH=~/…/python/07_the_run_dsl boukensha           # load step 7
  BOUKENSHA_DIR=~/projects/mybot/.boukensha boukensha          # custom config dir
  echo ~/…/python/08_the_repl_loop > ~/.boukensharc && boukensha  # permanent step default
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# This loader ships inside a step folder; its sibling ``boukensha/`` package is
# the bundled default.
_BUNDLED_DIR = Path(__file__).resolve().parent


def _abort(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def _has_package(step_dir: Path) -> bool:
    return (step_dir / "boukensha" / "__init__.py").exists()


def resolve() -> Path:
    """Return the step directory (containing a ``boukensha/`` package) to load."""
    # 1. Env var wins.
    env_path = os.environ.get("BOUKENSHA_PATH")
    if env_path:
        step_dir = Path(env_path).expanduser().resolve()
        if _has_package(step_dir):
            return step_dir
        _abort(
            "boukensha: BOUKENSHA_PATH is set but no boukensha/ package found at:\n"
            f"       {step_dir}\n"
            "       Make sure BOUKENSHA_PATH points to a step folder, e.g.:\n"
            "       BOUKENSHA_PATH=~/…/python/07_the_run_dsl boukensha"
        )

    # 2. ~/.boukensharc
    rc = Path.home() / ".boukensharc"
    if rc.exists():
        raw = rc.read_text(encoding="utf-8").strip()
        if raw:
            step_dir = Path(raw).expanduser().resolve()
            if _has_package(step_dir):
                return step_dir
            _abort(
                f"boukensha: ~/.boukensharc points to {raw}\n"
                "       but no boukensha/ package was found there.\n"
                "       Update ~/.boukensharc or remove it to use the bundled default."
            )

    # 3. Bundled default.
    return _BUNDLED_DIR


def load_and_start_repl() -> None:
    step_dir = resolve()

    if os.environ.get("BOUKENSHA_DEBUG"):
        print(f"[boukensha] loading from: {step_dir}")

    sys.path.insert(0, str(step_dir))
    import boukensha

    if not hasattr(boukensha, "repl"):
        _abort(
            f"boukensha: the step at {step_dir}\n"
            "       does not support the interactive REPL (added in step 7).\n"
            "       Point BOUKENSHA_PATH at step 7 or later."
        )

    boukensha.repl()


def main() -> None:
    load_and_start_repl()


if __name__ == "__main__":
    main()
