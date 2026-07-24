require_relative "client"

module Boukensha
  module MCP
    # Registers the tools of an MCP server with the agent.
    #
    # Domain-free: point it at a command and whatever that server advertises
    # through tools/list becomes agent tools. Tools::MudMcp is a preset over
    # this; a bootcamper plugs in an unrelated server with no new code.
    #
    # ## Stateful servers
    #
    # Some servers hold state that must be initialised before their other tools
    # work — a MUD login, a database connection, a browser session. MCP has no
    # capability flag for that; the channel it does provide is the
    # `instructions` string in the initialize handshake. This module folds that
    # into the system prompt, so the server explains its own lifecycle and the
    # agent acts on it, instead of the client hard-coding which tool comes first.
    #
    # after_connect: is only an optimisation over the same idea — calling the
    # bootstrap tool eagerly saves the agent a turn. It is a configured tool
    # name, not knowledge baked into this file.
    module Registrar
      # Tool names may only contain [a-zA-Z0-9_-] — a dot is rejected by the
      # provider APIs (verified against a live 400). So a namespaced tool reads
      # `server__tool`, the same convention MCP hosts use elsewhere.
      NAMESPACE_SEPARATOR = "__".freeze

      module_function

      # command:          argv for the server process (required)
      # env:              extra environment; a nil value removes that variable
      # only:/except:     restrict which advertised tools get registered
      # after_connect:    tool name to call once after connecting, e.g. "session_open"
      # use_instructions: append the server's handshake instructions to the system prompt
      # prefix:           namespace tools as "<prefix>__<tool>"
      # prefix_only:      nil namespaces every tool; an Array namespaces just
      #                   those names. MCP::Servers uses the Array form so only
      #                   tools that actually collide across servers get renamed
      #                   — everything else keeps the name the server published.
      #
      # Returns the Client so the caller can close it; a process-exit hook is
      # installed too so a server holding a connection is not left dangling.
      def register(registry,
                   command:,
                   env: {},
                   only: nil, except: nil,
                   after_connect: nil,
                   use_instructions: true,
                   prefix: nil, prefix_only: nil,
                   client: nil,
                   debug: false)
        # MCP::Servers connects every server up front so it can compute name
        # collisions before anything is registered, then hands the live client
        # in here. On the single-server path we connect it ourselves.
        own_client = client.nil?
        client ||= Client.new(command: command, env: env, debug: debug)
        client.start if own_client

        selected(client.tools, only: only, except: except).each do |descriptor|
          wanted = prefix && (prefix_only.nil? || prefix_only.include?(descriptor["name"]))
          register_one(registry, client, descriptor, prefix: wanted ? prefix : nil)
        end

        registry.context.append_system(client.instructions) if use_instructions

        if after_connect
          result = client.call_tool(after_connect, {})
          if debug || result.to_s.start_with?("error:")
            warn "[boukensha] mcp #{after_connect}: #{result}"
          end
        end

        at_exit { client.close }
        client
      end

      # Public so a multi-server manager can pre-compute namespaced names.
      def namespaced(prefix, name)
        prefix.nil? ? name.to_s : "#{prefix}#{NAMESPACE_SEPARATOR}#{name}"
      end

      # ---------- internals ----------

      def selected(tools, only:, except:)
        tools = tools.select { |t| Array(only).map(&:to_s).include?(t["name"]) } if only
        tools = tools.reject { |t| Array(except).map(&:to_s).include?(t["name"]) } if except
        tools
      end
      private_class_method :selected

      def register_one(registry, client, descriptor, prefix:)
        remote_name = descriptor["name"]
        local_name  = namespaced(prefix, remote_name)
        properties  = descriptor.dig("inputSchema", "properties") || {}

        # The agent sees local_name; the server is always called by its own
        # remote_name — prefixing is a client-side disambiguation, not something
        # the server knows about.
        registry.tool local_name,
                      description: descriptor["description"].to_s,
                      parameters:  properties do |**args|
          client.call_tool(remote_name, prune(args))
        end
      end
      private_class_method :register_one

      # Drop nil and blank arguments before they reach the server.
      #
      # BOUKENSHA's backends mark every declared parameter as required (see
      # Backends::Anthropic#to_tools), while MCP schemas have genuinely optional
      # fields. The model therefore fills optionals with "" to satisfy the
      # schema. Pruning turns that back into "argument omitted" — which belongs
      # here rather than in any one server's adapter: no MCP server means every
      # parameter to be mandatory.
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
