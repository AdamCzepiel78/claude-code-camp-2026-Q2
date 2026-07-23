"""Port of ``lib/boukensha/tools/file_system.rb``.

``register`` registers the standard set of file-oriented tools against a
registry, all sandboxed to a single root directory.

Tools registered:
  pwd              — return the working directory
  list_directory   — list files and subdirectories at a path
  read_file        — read the full contents of a file
  write_file       — write (or overwrite) a file
  delete_file      — delete a file
  search_files     — grep for a pattern across files in the working tree

Every path argument the agent supplies is resolved relative to that root. If
the resolved path would escape the root (path traversal) the tool returns an
error string rather than raising — so the agent sees it and can try something
sensible instead.

Usage (handled automatically by ``boukensha.run``/``boukensha.repl`` when
``working_dir`` is set, but it can be called directly too)::

    boukensha.tools.file_system.register(registry, working_dir="/my/project")
"""

from __future__ import annotations

import re
from pathlib import Path

from boukensha.registry import Registry


class _PathEscapeError(Exception):
    pass


def _resolve(root: Path, path: str) -> Path:
    absolute = (root / path).resolve()
    if not absolute.is_relative_to(root):
        raise _PathEscapeError(f"path '{path}' escapes the working directory")
    return absolute


def register(registry: Registry, *, working_dir: str | Path) -> None:
    root = Path(working_dir).expanduser().resolve()

    @registry.tool(
        "pwd",
        description="Return the working directory — the root that all file paths are relative to.",
        parameters={},
    )
    def pwd() -> str:
        return str(root)

    @registry.tool(
        "list_directory",
        description="List files and subdirectories at a path relative to the working directory. "
        "Defaults to the working directory itself.",
        parameters={
            "path": {"type": "string", "description": "Relative path to list (default '.')"},
        },
    )
    def list_directory(path: str = ".") -> str:
        try:
            target = _resolve(root, path)
        except _PathEscapeError as e:
            return f"error: {e}"
        if not target.is_dir():
            return f"error: '{path}' is not a directory"

        names = sorted(target.iterdir(), key=lambda p: p.name)
        entries = [f"{p.name}/" if p.is_dir() else p.name for p in names]
        return "\n".join(entries) if entries else "(empty)"

    @registry.tool(
        "read_file",
        description="Read and return the full contents of a file. Path is relative to the "
        "working directory.",
        parameters={
            "path": {"type": "string", "description": "Relative path to the file"},
        },
    )
    def read_file(path: str) -> str:
        try:
            target = _resolve(root, path)
        except _PathEscapeError as e:
            return f"error: {e}"
        if not target.is_file():
            return f"error: '{path}' is not a file"
        try:
            return target.read_text(encoding="utf-8")
        except OSError as e:
            return f"error: {e}"

    @registry.tool(
        "write_file",
        description="Write content to a file, creating it (and any missing parent directories) "
        "if needed, overwriting if it exists. Path is relative to the working directory.",
        parameters={
            "path": {"type": "string", "description": "Relative path to the file"},
            "content": {"type": "string", "description": "Text content to write"},
        },
    )
    def write_file(path: str, content: str) -> str:
        try:
            target = _resolve(root, path)
        except _PathEscapeError as e:
            return f"error: {e}"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as e:
            return f"error: {e}"
        rel = target.relative_to(root)
        return f"ok: wrote {len(content.encode('utf-8'))} bytes to {rel}"

    @registry.tool(
        "delete_file",
        description="Delete a file. Directories are not deleted. Path is relative to the "
        "working directory.",
        parameters={
            "path": {"type": "string", "description": "Relative path to the file to delete"},
        },
    )
    def delete_file(path: str) -> str:
        try:
            target = _resolve(root, path)
        except _PathEscapeError as e:
            return f"error: {e}"
        if not target.is_file():
            return f"error: '{path}' is not a file"
        try:
            target.unlink()
        except OSError as e:
            return f"error: {e}"
        return f"ok: deleted {path}"

    @registry.tool(
        "search_files",
        description="Search for a text pattern (literal string or Python regex) across all "
        "files in the working directory tree. Returns matching lines in "
        "'path:line_number:content' format.",
        parameters={
            "pattern": {"type": "string", "description": "The text or regex pattern to search for"},
            "path": {
                "type": "string",
                "description": "Subdirectory or file to search within (default '.' = entire "
                "working directory)",
            },
            "glob": {
                "type": "string",
                "description": "File glob to restrict which files are searched, e.g. '*.py' "
                "(default '*')",
            },
        },
    )
    def search_files(pattern: str, path: str = ".", glob: str = "*") -> str:
        try:
            target = _resolve(root, path)
        except _PathEscapeError as e:
            return f"error: {e}"

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f"error: invalid pattern: {e}"

        files = [target] if target.is_file() else sorted(
            p for p in target.rglob(glob) if p.is_file()
        )

        matches: list[str] = []
        for file in files:
            rel = file.relative_to(root)
            try:
                with file.open("r", encoding="utf-8", errors="replace") as fh:
                    for lineno, line in enumerate(fh, start=1):
                        if regex.search(line):
                            matches.append(f"{rel}:{lineno}:{line.rstrip(chr(10)).rstrip(chr(13))}")
            except OSError as e:
                matches.append(f"{rel}: error reading file: {e}")

        return "\n".join(matches) if matches else "no matches"
