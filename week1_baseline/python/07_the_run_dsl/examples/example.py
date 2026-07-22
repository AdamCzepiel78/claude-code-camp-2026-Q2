#!/usr/bin/env python3
"""Boukensha Step 7: The Run DSL — runnable smoke test.

Port of ``examples/example.rb``. Everything the earlier steps wired by hand —
Context, Registry, backend, PromptBuilder, Client, Logger, Agent — now collapses
into a single :func:`boukensha.run` call. Tools are declared in a ``setup``
callback that receives a ``RunDSL`` (the Python stand-in for Ruby's
``instance_eval`` block). Config (system prompt, model, provider, API key) is
loaded automatically from ``.boukensha`` / ``BOUKENSHA_DIR``.
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

    base_dir = Path(__file__).resolve().parent.parent

    def setup(t: RunDSL) -> None:
        @t.tool(
            "read_file",
            description="Read the contents of a file from disk",
            parameters={"path": {"type": "string", "description": "The file path to read"}},
        )
        def read_file(path: str) -> str:
            return (base_dir / path).read_text()

        @t.tool(
            "list_directory",
            description="List the files in a directory",
            parameters={"path": {"type": "string", "description": "The directory path to list"}},
        )
        def list_directory(path: str) -> str:
            return ", ".join(
                sorted(p.name for p in (base_dir / path).iterdir() if not p.name.startswith("."))
            )

    print("=== BOUKENSHA Step 7: The Boukensha.run DSL ===")
    print()
    print(f"Config: {boukensha.config()!r}")
    print()

    result = boukensha.run(
        task="Read the README.md file and summarise what this MUD player assistant framework can do.",
        setup=setup,
    )

    print()
    print("=== FINAL RESPONSE ===")
    print(result)


if __name__ == "__main__":
    main()
