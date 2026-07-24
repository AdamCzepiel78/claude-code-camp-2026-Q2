# MudManagerMcp

An MCP server for CircleMUD. The library *is* the server — `Session` and
`Primitives` are its internals, the protocol is its interface.

Responsibilities:

- manages long-lived telnet sessions
- manages the multi-step process of logging back in
- provides generic primitives for MUD commands
- serves all of the above over MCP, so agents in any language can drive a
  character without reimplementing the telnet layer (see
  [MCP server](#mcp-server))

## Build the Gem

From this directory:

```sh
gem build mud_manager_mcp.gemspec
gem install ./mud_manager_mcp-0.1.0.gem
```

Expected output:

```text
MudManagerMcp
```

## Uninstall

```sh
gem uninstall mud_manager_mcp
```

## Examples

Test the live session:

```sh
MUD_NAME=YourCharacterName MUD_PASSWORD=yourpassword ruby mud_manager_mcp/examples/live_session_test.rb
```

If you are already inside the `mud_manager_mcp` directory, run:

```sh
MUD_NAME=YourCharacterName MUD_PASSWORD=yourpassword ruby examples/live_session_test.rb
```

## MCP server

`bin/mud_manager_mcp` exposes the library over the
[Model Context Protocol](https://modelcontextprotocol.io) (JSON-RPC 2.0 over
stdio, protocol `2025-06-18`). It exists so bootcampers can write their agent in
Java, Python, Rust or Go without porting `session.rb`.

### Why a server rather than a port per language

Measured against the live tbaMUD server: **logging in costs ~5.9 s**, while a
command on an already-open session costs **~0.1 s** — a 61× difference. The MUD
also pushes output nobody asked for; sending `help` and then reading nothing for
three seconds still left 1,375 characters buffered. Both facts say the same
thing: **something must stay alive holding the socket.** A per-invocation CLI
cannot, so the server does.

The port-per-language alternative is not the 691 lines it looks like. 418 of
those (`primitives.rb`) are pure string building — mechanical to translate. The
risk is concentrated in `session.rb`'s 268 lines: a background reader thread,
a condition variable with timed waits, a telnet IAC state machine, and a
silence-window algorithm on a monotonic clock. Centralising exactly that file is
the point.

### Running it

Usually you do not run it by hand — an MCP client spawns it. Directly:

```sh
MUD_NAME=YourCharacterName MUD_PASSWORD=yourpassword bin/mud_manager_mcp
```

| Setting | Env | Flag | Default |
|---|---|---|---|
| Host | `MUD_HOST` | `--host` | `localhost` |
| Port | `MUD_PORT` | `--port` | `4000` |
| Character | `MUD_NAME` | `--name` | — |
| Password | `MUD_PASSWORD` | `--password` | — |
| Open session at startup | — | `--autoconnect` | off |
| Log protocol to stderr | `MUD_MCP_DEBUG` | `--debug` | off |

These are only *defaults*; a client can override any of them per call through
`session_open`.

For an MCP client that reads a JSON config (Claude Desktop, editors, …):

```json
{
  "mcpServers": {
    "mud": {
      "command": "ruby",
      "args": ["/abs/path/to/week1_baseline/mud_manager_mcp/bin/mud_manager_mcp"],
      "env": { "MUD_NAME": "YourCharacterName", "MUD_PASSWORD": "yourpassword" }
    }
  }
}
```

### Tools

31 tools in three groups:

- **Session lifecycle** — `session_open`, `session_close`, `session_list`,
  `session_status`
- **Low-level** — `send_raw`, `read_until_prompt`, `read_until_quiet`, `drain`
- **Gameplay** — `look`, `examine`, `check`, `move`, `flee`, `set_position`,
  `track`, `attack`, `skill_strike`, `consider`, `say`, `tell`, `channel_say`,
  `get_item`, `drop_item`, `put_item`, `equip_item`, `consume_item`,
  `cast_spell`, `use_magic_item`, `shop`, `practice`, `save_character`

The read primitives are deliberately first-class rather than hidden behind
"send a command, get its response". Because the MUD pushes output unprompted,
a caller needs a way to collect it without sending anything.

### Multi-session

Every tool takes an optional `session_id` (default `"default"`), so one server
process can drive several characters at once:

```jsonc
{"name": "session_open", "arguments": {"session_id": "healer", "name": "Cleric", "password": "…"}}
{"name": "look",         "arguments": {"session_id": "healer"}}
{"name": "attack",       "arguments": {"session_id": "default", "target": "goblin"}}
```

**A session is single-consumer.** `drain` is destructive — whoever reads first
empties the buffer — so two clients sharing one `session_id` will steal each
other's output. Give each consumer its own id.

Note that CircleMUD only allows one connection per character: opening a second
session as an *already-playing* character makes the server hand the connection
over ("Reconnecting") and kills the first. Multi-session means multiple
*characters*, not multiple connections to one.

### Errors

Two channels, deliberately:

- **Tool errors** come back as normal results with `isError: true` and text like
  `error: invalid direction: "sideways"`. The agent reads them and corrects
  itself — the same contract the in-process tools use.
- **Protocol errors** (unknown method, unknown tool) are JSON-RPC errors.

### Using it from an agent

Both BOUKENSHA step-10 ports ship an MCP client and source their MUD tools from
this server **by default**:

```ruby
Boukensha.run(task: "...")                  # ruby/10_standard_tool_library
Boukensha.run(task: "...", mud_mcp: false)  # in-process Tools::Mud instead
```

```python
boukensha.run(task="...")                   # python/10_standard_tool_library
boukensha.run(task="...", mud_mcp=False)    # in-process tools.Mud instead
```

Neither client restates a single tool name or description — they call
`tools/list` and register whatever comes back. Adding a tool here makes it
appear in every client, in every language, with no client change.
