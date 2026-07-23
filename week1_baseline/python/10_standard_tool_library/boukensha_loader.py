"""Port of ``lib/boukensha_loader.rb``.

Resolves which step folder to load the ``boukensha`` package from, then boots the
REPL. Kept as a *standalone* top-level module (not inside the ``boukensha``
package) so it can import a *different* step's ``boukensha`` package by name —
mirroring Ruby's ``lib/boukensha_loader.rb`` living outside ``lib/boukensha/``.

Resolution order:
  1. BOUKENSHA_PATH environment variable (selects which *step* dir to load)
  2. ~/.boukensharc  (a file containing a single path)
  3. The step directory this loader ships in (the bundled default — step 10)

"Loading a step" means: insert that step's directory (the one containing its
``boukensha/`` package) onto ``sys.path``, then ``import boukensha``.

The config directory (settings.yaml, .env, system.md) is separate — controlled by
BOUKENSHA_DIR (default ~/.boukensha).

MUD connection details come from settings.yaml (the ``mud:`` block) by default.
The legacy MUD_NAME / MUD_HOST / MUD_PORT / MUD_PASSWORD env vars are still
honoured and take precedence over config when set.

Examples:
  boukensha                                                    # bundled lib + ~/.boukensha
  BOUKENSHA_PATH=~/…/python/07_the_run_dsl boukensha           # load step 7
  BOUKENSHA_DIR=~/projects/mybot/.boukensha boukensha          # custom config dir
  echo ~/…/python/10_standard_tool_library > ~/.boukensharc && boukensha
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

    repl_kwargs: dict[str, object] = {}

    if os.environ.get("MUD_NAME"):
        # Legacy env-var override still works and takes precedence over config.
        password = os.environ.get("MUD_PASSWORD")
        if not password:
            _abort("boukensha: MUD_NAME is set but MUD_PASSWORD is missing.")
        repl_kwargs["working_dir"] = False
        repl_kwargs["mud"] = {
            "host": os.environ.get("MUD_HOST", "localhost"),
            "port": int(os.environ.get("MUD_PORT", "4000")),
            "name": os.environ["MUD_NAME"],
            "password": password,
        }
    # If MUD_NAME is not set, boukensha.repl() falls back to config.mud_*
    # values automatically (via _mud_opts_from_config inside boukensha.repl).

    boukensha.repl(**repl_kwargs)


def main() -> None:
    load_and_start_repl()


if __name__ == "__main__":
    main()
