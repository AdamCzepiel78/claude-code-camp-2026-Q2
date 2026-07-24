require_relative "registrar"

module Boukensha
  module MCP
    # Connect the agent to several MCP servers at once.
    #
    # One Registrar call wires up one server; nothing coordinates N. A real
    # agent wants more than one — a MUD *and* a Kubernetes server *and* a
    # filesystem server — which raises three problems this module owns:
    # name collisions between servers, collecting every server's instructions,
    # and closing them all on exit.
    #
    # ## Collision policy
    #
    # Two servers may both publish `search`. Colliding names are namespaced as
    # `<server>__<tool>`; names unique across all servers are left exactly as
    # the server published them. So connecting a second server never silently
    # renames the tools of the first unless there is a genuine clash.
    #
    # The separator is `__`, not `.` — tool names may only contain
    # [a-zA-Z0-9_-], and a dot is rejected by the provider APIs with a 400.
    module Servers
      module_function

      # specs: { "mud" => { command: [...], env: {...}, after_connect: "session_open" }, ... }
      #        The key names the server and becomes its namespace on collision.
      #
      # Returns [clients, provenance] — provenance is recorded in the session
      # log so it is afterwards visible which servers served which tools.
      def connect(registry, specs, debug: false)
        return [[], []] if specs.nil? || specs.empty?

        # Connect everything first: collisions can only be computed once every
        # server has told us what it offers.
        started = specs.map do |key, spec|
          spec   = normalise(spec)
          client = Client.new(command: spec[:command], env: spec[:env] || {}, debug: debug)
          client.start
          { key: key.to_s, spec: spec, client: client }
        end

        colliding = collisions(started)
        unless colliding.empty?
          warn "[boukensha] mcp tool-name collisions namespaced: #{colliding.sort.join(', ')}"
        end

        clients    = []
        provenance = []

        started.each do |entry|
          spec, client, key = entry[:spec], entry[:client], entry[:key]

          Registrar.register(
            registry,
            command:          spec[:command],
            env:              spec[:env] || {},
            only:             spec[:only],
            except:           spec[:except],
            after_connect:    spec[:after_connect],
            use_instructions: spec.fetch(:use_instructions, true),
            prefix:           key,
            prefix_only:      colliding,
            debug:            debug,
            client:           client            # already connected above
          )

          clients << client
          provenance << {
            name:           key,
            server:         client.server_info["name"],
            server_version: client.server_info["version"],
            tools:          client.tools.length
          }.compact
        end

        [clients, provenance]
      end

      # ---------- internals ----------

      def collisions(started)
        counts = Hash.new(0)
        started.each { |e| e[:client].tools.each { |t| counts[t["name"]] += 1 } }
        counts.select { |_, n| n > 1 }.keys
      end
      private_class_method :collisions

      def normalise(spec)
        spec.each_with_object({}) { |(k, v), out| out[k.to_sym] = v }
      end
      private_class_method :normalise
    end
  end
end
