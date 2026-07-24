require_relative "../mcp"

module Boukensha
  module Tools
    # Public entry point for MCP-sourced tools, sitting alongside
    # Tools::FileSystem and Tools::Shell so all tool registration reads the same
    # way. The implementation lives in Boukensha::MCP.
    #
    #   Boukensha::Tools::Mcp.register(registry,
    #     command: ["kubernetes-mcp-server", "--read-only"],
    #     except:  ["pods_delete"])
    #
    #   Boukensha::Tools::Mcp.connect(registry,
    #     "mud"   => { command: [...], after_connect: "session_open" },
    #     "notes" => { command: [...] })
    module Mcp
      module_function

      # One server. See MCP::Registrar for the options.
      def register(registry, **options)
        MCP::Registrar.register(registry, **options)
      end

      # Several servers at once, namespacing any tool name they both publish.
      # See MCP::Servers. Returns [clients, provenance].
      def connect(registry, specs, debug: false)
        MCP::Servers.connect(registry, specs, debug: debug)
      end
    end
  end
end
