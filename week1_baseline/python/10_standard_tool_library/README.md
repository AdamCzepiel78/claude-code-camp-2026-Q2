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

Registers gameplay tools (movement, combat, communication, inventory, magic,
shops, …) against a live CircleMUD session, backed by a vendored
`mud_manager` package. This is the **fallback** path now — see below.

### `boukensha.mcp` — a generic Model Context Protocol client

New. The agent is no longer coupled to the MUD specifically — it's coupled to
MCP, and the MUD is one server among any number that happen to speak it.

| | |
|---|---|
| `mcp.client.Client` | The protocol client — spawns a server, shakes hands, calls tools |
| `mcp.registrar` | Discovers one server's tools via `tools/list` and registers them all |
| `mcp.servers` | Drives several servers at once, namespacing tool-name collisions |

`boukensha.tools.mcp` is the public entry point (sits next to
`tools.file_system` and `tools.shell`); `boukensha.tools.mud_mcp` is a small
preset over it that points at the
[`mud_manager_mcp`](../../mud_manager_mcp) server (Ruby — spawned as a
subprocess; no Ruby knowledge needed to use it from Python).

```python
# Any MCP server — no MUD-specific code needed
boukensha.tools.mcp.register(registry,
    command=["kubernetes-mcp-server", "--read-only"],
    except_=["pods_delete"])

# Several at once, namespacing collisions as server__tool
boukensha.tools.mcp.connect(registry, {
    "mud":   {"command": [...], "after_connect": "session_open"},
    "notes": {"command": [...]},
})
```

Nothing here restates a tool name or description — whatever a server
advertises through `tools/list` becomes an agent tool automatically. A
stateful server (a MUD login, a database connection) explains its own
lifecycle through the MCP `instructions` handshake field, folded into the
system prompt via `Context.append_system` — the client never hard-codes which
tool to call first.

### MUD tools now come from `mud_manager_mcp` by default

`boukensha.tools.mud_mcp` replaces the in-process `boukensha.tools.mud` as
the default source of MUD gameplay tools. Instead of restating all 27+ tools
by hand in every language, the tools are defined once in the
[`mud_manager_mcp`](../../mud_manager_mcp) MCP server (Ruby) and discovered at
runtime — the same 31 tools every client gets, in any language.

```python
boukensha.run(task="...")                    # MUD tools via MCP (default)
boukensha.run(task="...", mud_mcp=False)     # old in-process tools.Mud instead
```

The in-process path (`tools.mud`, described above) is kept deliberately — as
a no-Ruby-subprocess fallback, and as the side-by-side comparison that makes
the MCP argument legible. Both paths register tools under the same names, so
they're mutually exclusive.

### Config-driven servers: `mcp_servers:` in `settings.yaml`

Additional MCP servers — on top of the MUD — can be declared in
`~/.boukensha/settings.yaml` instead of in code:

```yaml
mcp_servers:
  kubernetes:
    command: ["kubernetes-mcp-server", "--read-only"]
    except:  ["pods_delete"]
  notes:
    command: ["python3", "/path/to/notes_server.py"]
    after_connect: notes_open
```

```python
boukensha.run(task="...")                       # connects everything declared
boukensha.run(task="...", mcp_servers=False)    # connect none, even if declared
boukensha.run(task="...", mcp_servers={...})    # override the YAML block
```

A bootcamper plugs in a third-party MCP server with **zero new code**. The
MUD stays wired through its own `mud`/`mud_mcp` options rather than through
this block — it carries an in-process fallback and a REPL reachability probe
that a generic entry doesn't need — but its tools participate in the same
collision namespacing as anything declared here.

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

All modules can be registered manually if you need finer control:

```python
from boukensha import tools as Tools

Tools.FileSystem.register(registry, working_dir="/my/project")
Tools.Shell.register(registry, working_dir="/my/project", timeout=10, allowed_commands=["python"])
Tools.Mud.register(registry, host="localhost", port=4000, name="Gandalf", password="secret")
Tools.MudMcp.register(registry, name="Gandalf", password="secret")
```

## `mud_manager` — vendored, not pip-installed

This section covers the **in-process fallback** (`tools.mud`, `mud_mcp=False`).
The **default** path (`tools.mud_mcp`) doesn't need any of this — it spawns
[`mud_manager_mcp`](../../mud_manager_mcp)'s Ruby executable as a subprocess
and talks to it over MCP, so it needs `ruby` on `PATH` and that gem's
dependencies built (see its README), but nothing Python-side beyond the
`boukensha.mcp` client already described above.

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
