# MudManagerMcp — an MCP server for CircleMUD/tbaMUD.
#
# The JSON-RPC transport and the MCP lifecycle come from McpServer, vendored
# under lib/vendor (see lib/vendor/README.md) so this ships as one gem with no
# runtime dependency. What lives here is everything that makes this a *MUD*
# server:
#
#   Session          long-lived telnet connection, background buffering, IAC stripping
#   Primitives       stateless, typed CircleMUD command builders
#   SessionRegistry  several named sessions kept warm in one process
#   Tools            the MUD tool surface built on the above
#   ToolProvider     binds Tools to a registry for McpServer::Server
#
# Bootcampers writing an agent in Java, Python, Rust or Go talk to
# `bin/mud_manager_mcp` instead of porting the telnet layer.
module MudManagerMcp
  VERSION = "0.1.0".freeze

  # Handed to the client in the initialize handshake. MCP's `instructions` field
  # is the protocol's channel for "here is how to drive me" — a client can fold
  # it into the agent's system prompt, so the agent learns the session lifecycle
  # from the server rather than from hard-coded client code.
  INSTRUCTIONS = <<~TEXT.freeze
    Drives a CircleMUD/tbaMUD character over a live telnet session.
    Call session_open once before any gameplay tool — logging in takes about six
    seconds, and the session is then reused for every later call.
    Pass session_id to run several characters at once; omit it for 'default'.
    The MUD also emits output nobody asked for (combat rounds, arriving mobs,
    channel chatter). Use read_until_quiet or drain to collect it.
  TEXT
end

require_relative "vendor/mcp_server"  # the JSON-RPC transport (McpServer::Server)

require_relative "mud_manager_mcp/primitives"
require_relative "mud_manager_mcp/session"
require_relative "mud_manager_mcp/session_registry"
require_relative "mud_manager_mcp/tools"
require_relative "mud_manager_mcp/tool_provider"
