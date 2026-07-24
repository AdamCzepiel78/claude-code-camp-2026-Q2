Gem::Specification.new do |spec|
  spec.name        = "mcp_server"
  spec.version     = "0.1.0"
  spec.summary     = "McpServer — a domain-free Model Context Protocol server framework"
  spec.description = "Supplies the JSON-RPC 2.0 stdio transport and the MCP lifecycle " \
                     "(initialize handshake, tools/list, tools/call, notifications, error " \
                     "codes); you supply the tools. Identity, instructions, tool provider " \
                     "and shutdown hook are injected, so the same transport serves any " \
                     "domain. mud_manager_mcp is one consumer."
  spec.authors     = ["Andrew Brown"]
  spec.email       = ["andrew@exampro.co"]
  spec.license     = "MIT"

  spec.required_ruby_version = ">= 3.0"

  spec.files = Dir["lib/**/*.rb"]

  # No external dependencies — json is stdlib. The wire protocol is written out
  # by hand rather than pulled from an SDK, so it stays readable and the install
  # footprint stays zero.
end
