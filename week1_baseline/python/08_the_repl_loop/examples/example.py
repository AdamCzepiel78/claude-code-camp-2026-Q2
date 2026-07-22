#!/usr/bin/env python3
"""Boukensha Step 8: The REPL Loop — interactive session.

Port of ``examples/example.rb``. Instead of one-shot :func:`boukensha.run`, this
starts :func:`boukensha.repl`: register tools once in the ``setup`` callback,
then loop — reading tasks from stdin, running the agent, and printing replies —
with conversation history accumulating across turns. Config (system prompt,
model, provider, API key) is loaded automatically from ``.boukensha`` /
``BOUKENSHA_DIR``.

Type ``/help`` inside the REPL for the command list; ``/exit`` (or Ctrl-D) leaves.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow running this script directly without installing the package first,
# mirroring the Ruby example's `require_relative "../lib/boukensha"`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boukensha  # noqa: E402
from boukensha.run_dsl import RunDSL  # noqa: E402


def main() -> None:
    os.environ.setdefault(
        "BOUKENSHA_DIR", str(Path(__file__).resolve().parents[3] / ".boukensha")
    )

    # The base directory tools operate relative to — the step 7 folder makes a
    # good playground since it already has source files to read.
    base_dir = Path(__file__).resolve().parents[2] / "07_the_run_dsl"

    def setup(t: RunDSL) -> None:
        @t.tool(
            "read_file",
            description="Read the contents of a file from disk",
            parameters={
                "path": {
                    "type": "string",
                    "description": "File path (relative to the working directory)",
                }
            },
        )
        def read_file(path: str) -> str:
            return (base_dir / path).read_text()

        @t.tool(
            "list_directory",
            description="List the files in a directory",
            parameters={
                "path": {
                    "type": "string",
                    "description": "Directory path (relative to the working directory, or '.' for root)",
                }
            },
        )
        def list_directory(path: str) -> str:
            return ", ".join(
                sorted(p.name for p in (base_dir / path).iterdir() if not p.name.startswith("."))
            )

    print(f"Config: {boukensha.config()!r}")
    print()

    boukensha.repl(setup=setup)


if __name__ == "__main__":
    main()
