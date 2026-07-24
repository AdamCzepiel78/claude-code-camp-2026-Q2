# McpServer

A domain-free Model Context Protocol server framework. Supplies the JSON-RPC
2.0 stdio transport and the MCP lifecycle (initialize handshake, `tools/list`,
`tools/call`, notifications, error codes); you supply the tools.

There is nothing MUD-specific, filesystem-specific, or otherwise
domain-specific in this gem. [`mud_manager_mcp`](../mud_manager_mcp) is one
consumer, built on top of it — everything that makes that server *the MUD one*
lives in `mud_manager_mcp`, not here.

## Why this exists

`mud_manager_mcp`'s original server was 164 lines, of which 150 (91%) were
already domain-free JSON-RPC framing, handshake logic, and dispatch. Only 14
lines were genuinely coupled to the MUD (a server name constant, an
instructions string, a hard-referenced tool module, a shutdown hook). This gem
is that 91% pulled out, with the remaining 14 lines turned into constructor
arguments — `name:`, `version:`, `instructions:`, `tools:`, `on_shutdown:`.

The payoff: a bootcamper who wants to *write* an MCP server (rather than only
*consume* one) has something to build on, instead of copying boilerplate out
of a MUD project.

## Install

```sh
gem build mcp_server.gemspec
gem install ./mcp_server-0.1.0.gem
```

No external dependencies — `json` is stdlib. The wire protocol is written out
by hand rather than pulled from an SDK, so it stays small enough to read in
one sitting and the install footprint stays zero.

## Usage

```ruby
require "mcp_server"

tools = McpServer::ToolTable.new
tools.add("greet", "Say hello to someone.",
          { "name" => { "type" => "string", "description" => "Who to greet" } },
          required: ["name"]) { |args| "hello, #{args['name']}" }

McpServer::Server.new(
  tools:   tools,
  name:    "greeter",
  version: "1.0.0"
).run
```

That's a complete, working MCP server in eight lines.

### `McpServer::Server`

The transport. `STDOUT IS THE PROTOCOL` — nothing may write to it but this
class, which is why every diagnostic goes to stderr (`debug: true` to see
them) and a tool provider must use `warn` rather than `puts`.

```ruby
McpServer::Server.new(
  tools:        MyTools,              # any object answering the tool-provider contract
  name:         "my-server",
  version:      "1.0.0",
  instructions: "Call setup_thing first.",  # optional — folded into the initialize handshake
  on_shutdown:  -> { cleanup }              # optional — called once when stdin closes
).run
```

`instructions:` is the protocol's channel for "here is how to drive me" — which
tool to call first, what state this server holds. A client can fold it into
the agent's system prompt, so a stateful server explains its own lifecycle
instead of every client hard-coding it. `mud_manager_mcp` uses this to tell
agents to call `session_open` before anything else.

### Tool-provider contract

`tools:` is any object answering two methods:

```ruby
#descriptors        # -> Array of {"name" =>, "description" =>, "inputSchema" =>}
#call(name, args)   # -> [text, is_error]
```

`call` should return `[message, true]` for problems the *caller* could fix — a
bad argument, a missing precondition — so the agent reads the message and
corrects itself. Raise `KeyError` only for a genuinely unknown tool name; that
becomes a JSON-RPC error rather than a tool result.

### `McpServer::ToolTable`

A small builder for that contract, so you don't hand-assemble JSON Schema and
dispatch yourself. Using it is optional — implement the two methods directly
if you'd rather.

```ruby
tools = McpServer::ToolTable.new(rescuable: [ArgumentError])  # default

tools.add("note_add", "Append a note.",
          { "text" => { "type" => "string", "description" => "The note" } },
          required: ["text"]) { |args| store << args["text"]; "added" }
```

`rescuable:` names the exceptions a *caller* could plausibly fix. Those come
back as `isError` tool results carrying the message. Anything else propagates
and becomes a JSON-RPC internal error, because a bug in the server is not
something the agent can work around.

## Should the transport be ported per language?

Yes — deliberately the opposite call from `mud_manager_mcp`'s `Session`. The
telnet engine has 268 lines of genuine concurrency (a background reader
thread, condition variables with timed waits, an IAC state machine, a
silence-window algorithm); re-deriving that per language is a bug farm, so it
stays centralized in one Ruby gem that any language can spawn as a subprocess.

This transport has none of that. It's ~150 lines of "read a line, parse JSON,
dispatch, write a line" — no threads, no timing, no protocol state beyond a
boolean. Porting it is mechanical, and it's what lets a Python (or Go, or
Rust) bootcamper write their *own* MCP server without touching Ruby at all.
See [`python/mcp_server`](../python/mcp_server) for the second reference
implementation.

## Who uses this

This is the **canonical source** for the transport. Two things build on it:

- [`mud_manager_mcp`](../mud_manager_mcp) **vendors** these files (byte-identical
  copies under its `lib/vendor/`) so it can ship as a single self-contained gem
  with no runtime dependency. Its `tasks/verify_vendor.rb` diffs the copies
  against this directory and fails on drift — so this stays the one place the
  transport is edited.
- [`python/mcp_server`](../python/mcp_server) is the Python port of the same
  framework.

Nothing here refers to either consumer — the code is domain-free. Any Ruby
program can `require "mcp_server"` (or vendor it the same way) and expose its
own tools over MCP.
