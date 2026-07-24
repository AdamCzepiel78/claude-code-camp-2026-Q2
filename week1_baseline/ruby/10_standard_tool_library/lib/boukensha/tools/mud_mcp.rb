require_relative "../mcp_client"

module Boukensha
  module Tools
    # MUD tools sourced from the mud_manager_mcp server. This is the default path
    # for MUD play; tools/mud.rb remains as the in-process alternative.
    #
    # Compare the two: tools/mud.rb hard-codes 27 tools — every name, description
    # and parameter schema — and its Python twin restates all of it again. This
    # file states none of them. It asks the server what it offers and registers
    # whatever comes back, so a tool added to the server appears in the agent
    # with no client change, in any language.
    #
    # That is the whole argument for the MCP layer: the telnet session, reader
    # thread and IAC handling still have to exist — they live inside
    # mud_manager_mcp — but the per-language duplication of the tool
    # *descriptions* on top of them does not.
    #
    # Usage:
    #
    #   Boukensha::Tools::MudMcp.register(registry, name: "dummy", password: "secret")
    #
    # Returns the McpClient so the caller can close it; a process-exit hook is
    # installed too so the MUD connection is not left dangling.
    module MudMcp
      # week1_baseline/mud_manager_mcp/bin/mud_manager_mcp, relative to this file.
      # Used in preference to the gem-installed executable so the step runs
      # straight from a checkout, with no `gem install` step.
      DEFAULT_SERVER = File.expand_path(
        "../../../../../mud_manager_mcp/bin/mud_manager_mcp", __dir__
      ).freeze

      module_function

      def register(registry,
                   host: nil, port: nil, name: nil, password: nil,
                   command: nil, autoconnect: true,
                   only: nil, except: nil, debug: false)
        command ||= default_command

        client = McpClient.new(
          command: command,
          env: connection_env(host: host, port: port, name: name, password: password),
          debug: debug
        )
        client.start

        selected(client.tools, only: only, except: except).each do |descriptor|
          register_one(registry, client, descriptor)
        end

        # Pay the ~6s MUD login now rather than inside the agent's first tool
        # call. Non-fatal: the agent can still call session_open and read the
        # real error, which is why this warns instead of raising.
        if autoconnect
          result = client.call_tool("session_open", {})
          warn "[boukensha] MUD session_open: #{result}" if debug || result.start_with?("error:")
        end

        at_exit { client.close }
        client
      end

      # ---------- internals ----------

      def default_command
        if (override = ENV["BOUKENSHA_MUD_MCP_COMMAND"])
          return override.split
        end

        ["ruby", DEFAULT_SERVER]
      end
      private_class_method :default_command

      def connection_env(host:, port:, name:, password:)
        {
          "MUD_HOST"     => host,
          "MUD_PORT"     => port,
          "MUD_NAME"     => name,
          "MUD_PASSWORD" => password
        }.compact
      end
      private_class_method :connection_env

      def selected(tools, only:, except:)
        tools = tools.select { |t| Array(only).map(&:to_s).include?(t["name"]) } if only
        tools = tools.reject { |t| Array(except).map(&:to_s).include?(t["name"]) } if except
        tools
      end
      private_class_method :selected

      def register_one(registry, client, descriptor)
        name       = descriptor["name"]
        properties = descriptor.dig("inputSchema", "properties") || {}

        registry.tool name,
                      description: descriptor["description"].to_s,
                      parameters:  properties do |**args|
          client.call_tool(name, prune(args))
        end
      end
      private_class_method :register_one

      # Drop nil and blank arguments before they reach the server.
      #
      # BOUKENSHA's backends mark every declared parameter as required (see
      # Backends::Anthropic#to_tools), but MCP schemas have genuinely optional
      # fields — session_id everywhere, and `look` takes none at all. The model
      # therefore tends to fill optionals with "" to satisfy the schema. Pruning
      # here turns that back into "argument omitted", so `look` with a blank
      # target describes the room instead of hunting for an object named "".
      def prune(args)
        args.each_with_object({}) do |(key, value), out|
          next if value.nil?
          next if value.is_a?(String) && value.strip.empty?

          out[key.to_s] = value
        end
      end
      private_class_method :prune
    end
  end
end
