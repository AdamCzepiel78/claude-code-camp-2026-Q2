require_relative "mcp/client"
require_relative "mcp/registrar"
require_relative "mcp/servers"

module Boukensha
  # BOUKENSHA's Model Context Protocol client side.
  #
  #   MCP::Client     the protocol client — spawn a server, handshake, call tools
  #   MCP::Registrar  turn one server's advertised tools into agent tools
  #   MCP::Servers    drive several servers at once, namespacing collisions
  #
  # Tools::Mcp is the public entry point that sits alongside Tools::FileSystem
  # and Tools::Shell; Tools::MudMcp is a preset over it. Everything here is
  # domain-free — the MUD is one server among any number.
  module MCP
  end
end
