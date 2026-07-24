# 10 · A Standard Tool Library (Python port)

Python 3 port of [`ruby/10_standard_tool_library`](../../ruby/10_standard_tool_library/README.md).
Same design — see the Ruby README for the full rationale. This document covers the
Python-specific implementation.

Boukensha now ships two built-in tool modules plus a MUD gameplay module. Instead of
manually registering tools, a real coding harness gives the agent a standard library
of capabilities out of the box.

## What's new

### `boukensha.tools.file_system`

The evolution of step 9's `working_dir`-scoped file tools — five tools plus one new
one. Registers automatically when `working_dir` is set:

| Tool | Description |
|------|-------------|
| `pwd` | Return the working directory |
| `list_directory` | List files at a path (default `.`) |
| `read_file` | Read a file's contents |
| `write_file` | Write (or create) a file |
| `delete_file` | Delete a file |
| `search_files` | **New** — regex-search across the working tree, returns `path:line:content` matches |

All paths are **relative to the working directory**. Absolute paths and `..`
traversals that escape the root are rejected with an error string (checked via
`Path.resolve()` + `Path.is_relative_to()`).

### `boukensha.tools.shell`

New module. Registers automatically when `working_dir` is set:

| Tool | Description |
|------|-------------|
| `run_command` | Run a shell command inside the working directory |

Commands run with a configurable timeout (`subprocess.run(..., timeout=...)`) and an
optional allow-list of permitted executables.

### `boukensha.tools.mud`

New module. Registers gameplay tools (movement, combat, communication, inventory,
magic, shops, …) against a live CircleMUD session, backed by a vendored
`mud_manager` package.

### New `boukensha.run` / `boukensha.repl` keyword arguments

```python
boukensha.run(
    task="...",
    working_dir="/my/project",
    allowed_commands=["python", "git", "pytest"],  # None = allow all (default)
    shell_timeout=30,                                # seconds, default 30
)
```

`allowed_commands=None` permits any executable. Pass an explicit list to lock the
agent down:

```python
# Only allow python and git — rm, curl, etc. will be rejected
boukensha.run(task="...", allowed_commands=["python", "git"])
```

### Direct registration

All three modules can be registered manually if you need finer control:

```python
from boukensha import tools as Tools

Tools.FileSystem.register(registry, working_dir="/my/project")
Tools.Shell.register(registry, working_dir="/my/project", timeout=10, allowed_commands=["python"])
Tools.Mud.register(registry, host="localhost", port=4000, name="Gandalf", password="secret")
```

## `mud_manager` — vendored, not pip-installed

Ruby's `mud_manager` is a real (if unpublished) gem, vendored in this repo at
`week1_baseline/mud_manager_mcp` and pulled in via the gemspec as a dependency. There is
no PyPI equivalent, so the Python port vendors a translated copy at
**`python/mud_manager/`** — a sibling of every step directory (`00_config`,
`01_struct_skeleton`, … `10_standard_tool_library`), not nested inside this step.
This mirrors the Ruby structure, where `mud_manager` is its own package rather than
duplicated per lesson.

`boukensha/tools/mud.py` adds `python/` (its own parent's parent's parent) onto
`sys.path` before `import mud_manager`, so no installation step is needed — it works
the same way `boukensha_loader.py` resolves a step directory onto `sys.path`. Both
`mud_manager/session.py` (the telnet session) and `mud_manager/primitives.py` (the
CircleMUD command builders) use only the standard library (`socket`, `threading`,
`re`) — no new dependencies.

## Run the demo

```sh
python examples/example.py

# or via the global executable pointed at this step:
BOUKENSHA_PATH=~/…/python/10_standard_tool_library boukensha
```
