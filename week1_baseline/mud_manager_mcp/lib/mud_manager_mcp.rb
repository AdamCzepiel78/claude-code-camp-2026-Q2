# MudManagerMcp — an MCP server for CircleMUD/tbaMUD.
#
# The library *is* the server: Session and Primitives are its internals, and the
# Model Context Protocol is how anything outside Ruby reaches them. Bootcampers
# writing an agent in Java, Python, Rust or Go talk to `bin/mud_manager_mcp`
# instead of porting the telnet layer.
#
#   Session          long-lived telnet connection, background buffering, IAC stripping
#   Primitives       stateless, typed CircleMUD command builders
#   SessionRegistry  several named sessions kept warm in one process
#   Tools            the MCP tool surface built on the above
#   Server           JSON-RPC 2.0 over stdio
module MudManagerMcp
end

require_relative "mud_manager_mcp/primitives"
require_relative "mud_manager_mcp/session"
require_relative "mud_manager_mcp/session_registry"
require_relative "mud_manager_mcp/tools"
require_relative "mud_manager_mcp/server"
