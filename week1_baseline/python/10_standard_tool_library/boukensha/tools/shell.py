"""Port of ``lib/boukensha/tools/shell.rb``.

``register`` registers command-execution tools against a registry.

Tools registered:
  run_command  — run an arbitrary shell command inside the working directory

Options:
  working_dir:      (required) all commands run with this as their cwd
  timeout:          seconds before a command is killed (default 30)
  allowed_commands: optional list of allowed executable names (e.g. ["python", "git"]).
                    When None (the default) all commands are permitted. When set,
                    any command whose first token is not in the list is rejected
                    before execution.

Usage (handled automatically by ``boukensha.run``/``boukensha.repl`` when
``working_dir`` is set)::

    boukensha.tools.shell.register(
        registry,
        working_dir="/my/project",
        allowed_commands=["python", "pytest", "git"],
    )
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from boukensha.registry import Registry


def register(
    registry: Registry,
    *,
    working_dir: str | Path,
    timeout: int = 30,
    allowed_commands: list[str] | None = None,
) -> None:
    root = Path(working_dir).expanduser().resolve()

    allow_note = f" Allowed executables: {', '.join(allowed_commands)}." if allowed_commands else ""

    @registry.tool(
        "run_command",
        description="Run a shell command inside the working directory and return its combined "
        f"stdout+stderr output. Commands run with a {timeout}-second timeout.{allow_note}",
        parameters={
            "command": {
                "type": "string",
                "description": "The shell command to execute (e.g. 'python script.py', "
                "'ls -la', 'git status')",
            },
        },
    )
    def run_command(command: str) -> str:
        if allowed_commands is not None:
            executable = command.strip().split()[0] if command.strip() else ""
            if executable not in allowed_commands:
                allowed = ", ".join(allowed_commands)
                return f"error: '{executable}' is not in the allowed-commands list ({allowed})"

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=root,
                timeout=timeout,
                capture_output=True,
                text=True,
            )
        except subprocess.TimeoutExpired:
            return f"error: command timed out after {timeout}s: {command}"
        except OSError as e:
            return f"error: {e}"

        output = (result.stdout + result.stderr).strip()
        exit_note = "" if result.returncode == 0 else f"\n[exit {result.returncode}]"
        return f"(no output){exit_note}" if not output else f"{output}{exit_note}"
