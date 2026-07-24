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

  # No runtime dependencies. The JSON-RPC transport and MCP lifecycle
  # (McpServer) are vendored under lib/vendor — byte-identical copies of the
  # standalone mcp_server gem, which stays the canonical source (see
  # lib/vendor/README.md). This keeps mud_manager_mcp a single self-contained
  # gem: `gem install mud_manager_mcp` pulls nothing else and bin/mud_manager_mcp
  # runs from this gem alone.
  #
  # The vendored files are picked up by the lib/**/*.rb glob below; socket,
  # thread and optparse are stdlib, and McpServer writes JSON-RPC 2.0 by hand
  # rather than pulling in an SDK, so the install footprint stays zero.
  spec.files       = Dir["lib/**/*.rb"] + Dir["bin/*"]
  spec.bindir      = "bin"
  spec.executables = ["mud_manager_mcp"]
end
