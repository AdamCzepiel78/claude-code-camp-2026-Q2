# Step 10 — A Standard Tool Library

Boukensha now ships two built-in tool modules, plus a generic Model Context
Protocol (MCP) client. Instead of manually registering tools, a real coding
harness gives the agent a standard library of capabilities out of the box —
and instead of hand-coding every third-party tool surface, it can plug into
*any* MCP server through configuration alone.

## What's new

### `Boukensha::Tools::FileSystem`

The evolution of step 9's `WorkingDirectory` — same five tools plus one new one. Registers automatically when `working_dir:` is set:

| Tool | Description |
|------|-------------|
| `pwd` | Return the working directory |
| `list_directory` | List files at a path (default `.`) |
| `read_file` | Read a file's contents |
| `write_file` | Write (or create) a file |
| `delete_file` | Delete a file |
| `search_files` | **New** — grep for a regex pattern across the working tree, returns `path:line:content` matches |

All paths are **relative to the working directory**. Absolute paths and `..` traversals that escape the root are rejected with an error string.

### `Boukensha::Tools::Shell`

New module. Registers automatically when `working_dir:` is set:

| Tool | Description |
|------|-------------|
| `run_command` | Run a shell command inside the working directory |

Commands run with a configurable timeout and an optional allow-list of permitted executables.

### `Boukensha::MCP` — a generic Model Context Protocol client

New. The agent is no longer coupled to the MUD specifically — it's coupled to
MCP, and the MUD is one server among any number that happen to speak it.

| | |
|---|---|
| `MCP::Client` | The protocol client — spawns a server, shakes hands, calls tools |
| `MCP::Registrar` | Discovers one server's tools via `tools/list` and registers them all |
| `MCP::Servers` | Drives several servers at once, namespacing tool-name collisions |

`Tools::Mcp` is the public entry point (sits next to `Tools::FileSystem` and
`Tools::Shell`); `Tools::MudMcp` is a ~30-line preset over it that points at
the [`mud_manager_mcp`](../../mud_manager_mcp) server.

```ruby
# Any MCP server — no MUD-specific code needed
Boukensha::Tools::Mcp.register(registry,
  command: ["kubernetes-mcp-server", "--read-only"],
  except:  ["pods_delete"])

# Several at once, namespacing collisions as server__tool
Boukensha::Tools::Mcp.connect(registry,
  "mud"   => { command: [...], after_connect: "session_open" },
  "notes" => { command: [...] })
```

Nothing here restates a tool name or description — whatever a server
advertises through `tools/list` becomes an agent tool automatically. A
stateful server (a MUD login, a database connection) explains its own
lifecycle through the MCP `instructions` handshake field, which gets folded
into the system prompt (`Context#append_system`) — the client never
hard-codes which tool to call first.

### MUD tools now come from `mud_manager_mcp` by default

`Boukensha::Tools::MudMcp` replaces the old in-process `Tools::Mud` as the
default source of MUD gameplay tools. Instead of restating all 27+ tools by
hand in every language, the tools are defined once in the
[`mud_manager_mcp`](../../mud_manager_mcp) MCP server and discovered at
runtime — the same 31 tools every client gets, in any language.

```ruby
Boukensha.run(task: "...")                  # MUD tools via MCP (default)
Boukensha.run(task: "...", mud_mcp: false)  # old in-process Tools::Mud instead
```

The in-process path is kept deliberately — as a no-Ruby-subprocess fallback,
and as the side-by-side comparison that makes the MCP argument legible. Both
paths register tools under the same names, so they're mutually exclusive.

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

```ruby
Boukensha.run(task: "...")                    # connects everything declared
Boukensha.run(task: "...", mcp_servers: false) # connect none, even if declared
Boukensha.run(task: "...", mcp_servers: {...}) # override the YAML block
```

A bootcamper plugs in a third-party MCP server with **zero new code**. The
MUD stays wired through its own `mud:`/`mud_mcp:` options rather than through
this block — it carries an in-process fallback and a REPL reachability probe
that a generic entry doesn't need — but its tools participate in the same
collision namespacing as anything declared here.

### New `Boukensha.run` / `Boukensha.repl` keyword arguments

```ruby
Boukensha.run(
  task:             "...",
  working_dir:      "/my/project",
  allowed_commands: ["ruby", "git", "bundle"],  # nil = allow all (default)
  shell_timeout:    30                           # seconds, default 30
)
```

`allowed_commands: nil` permits any executable. Pass an explicit list to lock the agent down:

```ruby
# Only allow ruby and git — rm, curl, etc. will be rejected
Boukensha.run(task: "...", allowed_commands: ["ruby", "git"])
```

### Direct registration

All modules can be registered manually if you need finer control:

```ruby
Boukensha::Tools::FileSystem.register(registry, working_dir: "/my/project")
Boukensha::Tools::Shell.register(registry, working_dir: "/my/project",
                              timeout: 10, allowed_commands: ["ruby"])
Boukensha::Tools::MudMcp.register(registry, name: "Gandalf", password: "secret")
```

## Run the demo

```sh
ruby examples/example.rb

# or via the global executable pointed at this step:
BOUKENSHA_PATH=~/Sites/boukensha/10_standard_tool_library boukensha
```

### Building the gem

`boukensha` depends on [`mud_manager_mcp`](../../mud_manager_mcp), which is a
single self-contained gem (the MCP transport is vendored inside it — no
`mcp_server` gem to install). Build and install the two, in order:

```sh
cd ../../mud_manager_mcp             && gem build mud_manager_mcp.gemspec && gem install ./mud_manager_mcp-0.1.0.gem
cd ../ruby/10_standard_tool_library && gem build boukensha.gemspec       && gem install ./boukensha-0.10.0.gem
```

`Tools::MudMcp` prefers running `mud_manager_mcp`'s executable straight from a
checkout (no `gem install` needed) via a relative path from this step's
`lib/`. When that path doesn't exist — i.e. when `boukensha` itself is running
as an installed gem, with no sibling checkout nearby — it falls back to
`Gem.bin_path("mud_manager_mcp", "mud_manager_mcp")`, which the dependency
above guarantees is present.

## Technical Considerations

This is just observations we dont want to fix these right now just to perserve current
future layers.
- There could be a case where if a sessions is already is in used for a user they are
prompted with Yes or No to kill the session and our agent's/mud_manager doesn't have a way
to handle that case.

