Gem::Specification.new do |spec|
  spec.name        = "mud_manager_mcp"
  spec.version     = "0.1.0"
  spec.summary     = "MudManagerMcp — an MCP server for CircleMUD"
  spec.description = "An MCP server that drives one or more CircleMUD characters over JSON-RPC, " \
                     "so agents written in any language can play without reimplementing the " \
                     "telnet layer. MudManagerMcp::Session (a long-lived connection with " \
                     "background buffering and IAC stripping) and MudManagerMcp::Primitives " \
                     "(typed CircleMUD command builders) are its internals; the protocol is " \
                     "the interface."
  spec.authors     = ["Andrew Brown"]
  spec.email       = ["andrew@exampro.co"]
  spec.license     = "MIT"

  spec.required_ruby_version = ">= 3.0"

  # The JSON-RPC transport and MCP lifecycle live in a domain-free gem; this
  # gem supplies only the MUD half (session, primitives, tools).
  spec.add_dependency "mcp_server", "~> 0.1"

  spec.files       = Dir["lib/**/*.rb"] + Dir["bin/*"]
  spec.bindir      = "bin"
  spec.executables = ["mud_manager_mcp"]

  # No third-party dependencies beyond that — socket, thread and optparse are
  # stdlib, and mcp_server writes JSON-RPC 2.0 by hand rather than pulling in
  # an SDK, keeping the wire protocol readable and the install footprint zero.
end
