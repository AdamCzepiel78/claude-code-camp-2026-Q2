# mcp_server (Python port)

Python 3 port of [`../mcp_server`](../../mcp_server/README.md) (Ruby). Same
design — see the Ruby README for the full rationale. A domain-free Model
Context Protocol server framework: supplies the JSON-RPC 2.0 stdio transport
and the MCP lifecycle; you supply the tools.

There is nothing MUD-specific here. `mud_manager_mcp` (Ruby) is one consumer,
built on the Ruby gem — this Python port exists so non-Ruby bootcampers can
write their *own* MCP server without touching Ruby at all. It's a second
reference implementation, not a dependency of anything else in this repo.

## Why porting the transport (but not the MUD engine) is cheap

`mud_manager_mcp`'s telnet engine (`Session`) has ~268 lines of genuine
concurrency — a background reader thread, condition variables with timed
waits, an IAC state machine, a silence-window algorithm on a monotonic clock.
Re-deriving that per language is a bug farm, so it stays centralized in Ruby;
every language spawns it as a subprocess instead.

This transport has none of that. It's ~150 lines of "read a line, parse JSON,
dispatch, write a line" — no threads, no timing, no protocol state beyond a
boolean. Porting it is mechanical, which is the whole point: it's what lets a
Python bootcamper write an MCP server in Python.

## Usage

```python
from mcp_server import Server, ToolTable

tools = ToolTable()

@tools.add("greet", "Say hello.", {"name": {"type": "string"}}, required=["name"])
def greet(args):
    return f"hello, {args['name']}"

Server(tools=tools, name="greeter", version="1.0.0").run()
```

That's a complete, working MCP server.

### `Server`

The transport. Nothing may write to stdout but this class — every diagnostic
goes to stderr (`debug=True` to see them), and a tool handler must use
`print(..., file=sys.stderr)` rather than plain `print`.

```python
Server(
    tools=my_tools,                    # any object with descriptors()/call(name, args)
    name="my-server",
    version="1.0.0",
    instructions="Call setup_thing first.",  # optional — folded into the initialize handshake
    on_shutdown=lambda: cleanup(),           # optional — called once when stdin closes
).run()
```

`instructions` is the protocol's channel for "here is how to drive me" — which
tool to call first, what state this server holds. A client can fold it into
the agent's system prompt, so a stateful server explains its own lifecycle
instead of every client hard-coding it.

### Tool-provider contract

`tools=` is any object with two methods:

```python
descriptors() -> list[dict]              # [{"name": ..., "description": ..., "inputSchema": ...}, ...]
call(name, args) -> tuple[str, bool]     # (text, is_error)
```

`call` should return `(message, True)` for problems the *caller* could fix — a
bad argument, a missing precondition — so the agent reads the message and
corrects itself. Raise `KeyError` only for a genuinely unknown tool name; that
becomes a JSON-RPC error rather than a tool result.

### `ToolTable`

A small builder for that contract, used as a decorator factory so metadata
reads before the handler body:

```python
tools = ToolTable(rescuable=(ValueError,))  # default

@tools.add("note_add", "Append a note.",
           {"text": {"type": "string", "description": "The note"}},
           required=["text"])
def note_add(args):
    store.append(args["text"])
    return "added"
```

`rescuable` names the exceptions a *caller* could plausibly fix. Those come
back as `isError` tool results carrying the message. Anything else propagates
and becomes a JSON-RPC internal error, because a bug in the server is not
something the agent can work around.

## Files

```
mcp_server/
├── __init__.py     re-exports Server, ToolTable, RpcError, protocol constants
├── server.py        the transport (Server, RpcError, JSON-RPC error codes)
└── tool_table.py     the ToolTable builder
```

No third-party dependencies — `json`, `sys`, `dataclasses` are stdlib.
