require_relative "mcp"

module Boukensha
  module Tools
    # MUD preset over the generic Tools::Mcp.
    #
    # Everything that makes this "the MUD one" lives here, and it is all
    # configuration: which binary to start, which environment variables carry
    # the credentials, and which tool is worth calling eagerly. The registration
    # machinery — discovery, filtering, argument pruning, cleanup — is generic
    # and lives in Tools::Mcp.
    #
    # That split is the point. The agent is not coupled to MUDs; it is coupled
    # to MCP, and this file is the ~30 lines of configuration that aim it at one
    # particular server.
    #
    #   Boukensha::Tools::MudMcp.register(registry, name: "dummy", password: "secret")
    module MudMcp
      # week1_baseline/mud_manager_mcp/bin/mud_manager_mcp, relative to this file.
      # Preferred over the gem-installed executable so the step runs straight
      # from a checkout, with no `gem install` step.
      DEFAULT_SERVER = File.expand_path(
        "../../../../../mud_manager_mcp/bin/mud_manager_mcp", __dir__
      ).freeze

      # The MUD login costs ~6s. Paying it at registration keeps it out of the
      # agent's first tool call. The server also states this in its handshake
      # instructions, so an agent would get there on its own — this only saves
      # the turn.
      BOOTSTRAP_TOOL = "session_open".freeze

      module_function

      def register(registry,
                   host: nil, port: nil, name: nil, password: nil,
                   command: nil, autoconnect: true,
                   only: nil, except: nil, debug: false)
        Mcp.register(
          registry,
          command:       command || default_command,
          env:           server_env(host: host, port: port, name: name,
                                    password: password, debug: debug),
          only:          only,
          except:        except,
          after_connect: autoconnect ? BOOTSTRAP_TOOL : nil,
          debug:         debug
        )
      end

      # ---------- internals ----------

      def default_command
        if (override = ENV["BOUKENSHA_MUD_MCP_COMMAND"])
          return override.split
        end

        ["ruby", DEFAULT_SERVER]
      end
      private_class_method :default_command

      def server_env(host:, port:, name:, password:, debug:)
        env = {
          "MUD_HOST"     => host,
          "MUD_PORT"     => port,
          "MUD_NAME"     => name,
          "MUD_PASSWORD" => password
        }.compact

        # One debug switch, not two: the client's `debug` forwards the server's
        # stderr, and this makes the server actually say something.
        env["MUD_MCP_DEBUG"] = "1" if debug

        # The server is a standalone script with no Gemfile. Spawned from inside
        # `bundle exec` it would inherit BUNDLE_*/RUBYOPT, re-initialise bundler
        # and bury its own logging under constant-redefinition warnings. nil
        # removes the variable from the child.
        %w[BUNDLE_GEMFILE BUNDLE_BIN_PATH BUNDLE_PATH RUBYOPT].each { |key| env[key] = nil }

        env
      end
      private_class_method :server_env
    end
  end
end
