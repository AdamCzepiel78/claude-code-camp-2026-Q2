# McpServer — a domain-free Model Context Protocol server framework.
#
# Supplies the JSON-RPC 2.0 transport and the MCP lifecycle; you supply the
# tools. `mud_manager_mcp` is one consumer, but nothing here knows about MUDs.
#
#   require "mcp_server"
#
#   TOOLS = McpServer::ToolTable.new
#   TOOLS.add("greet", "Say hello to someone.",
#             { "name" => { "type" => "string", "description" => "Who to greet" } },
#             required: ["name"]) { |args| "hello, #{args['name']}" }
#
#   McpServer::Server.new(tools: TOOLS, name: "greeter", version: "1.0.0").run
#
# ToolTable is a convenience — any object answering #descriptors and
# #call(name, args) works. See McpServer::Server for that contract.
module McpServer
end

require_relative "mcp_server/tool_table"
require_relative "mcp_server/server"
