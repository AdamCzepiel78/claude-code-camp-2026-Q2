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

  spec.files       = Dir["lib/**/*.rb"] + Dir["bin/*"]
  spec.bindir      = "bin"
  spec.executables = ["mud_manager_mcp"]

  # Still no external dependencies — socket, thread, json and optparse are all
  # stdlib. The MCP server speaks JSON-RPC 2.0 by hand rather than pulling in
  # an SDK, keeping the wire protocol readable and the install footprint zero.
end
