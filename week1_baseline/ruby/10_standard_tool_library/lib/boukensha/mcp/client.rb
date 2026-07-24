require "json"
require "open3"
require "timeout"

module Boukensha
  module MCP
  # A minimal Model Context Protocol client speaking JSON-RPC 2.0 over a
  # subprocess's stdin/stdout.
  #
  # Hand-rolled for the same reason the rest of BOUKENSHA is: the protocol is
  # small enough to read, and an MCP server is just a program you talk to over
  # two pipes. Spawn it, shake hands, ask what tools it has, call them.
  #
  # This is the piece that makes tool code language-neutral. The MUD tools are
  # defined once, in the mud_manager MCP server; this client discovers them at
  # runtime rather than restating them — which is why the Python port of this
  # file registers the identical tool set without duplicating a single
  # description.
    class Client
      PROTOCOL_VERSION = "2025-06-18".freeze

      class Error < StandardError; end
      class ProtocolError < Error; end

      attr_reader :server_info, :instructions

      # command: argv for the server process, e.g. ["ruby", "/path/bin/mud_manager_mcp"]
      # env:     extra environment for it (MUD_NAME, MUD_PASSWORD, …)
      # timeout: seconds to wait for any single response. Generous by default —
      #          session_open pays a ~6s MUD login.
      # A nil value in env *removes* that variable from the child's environment
      # (Open3 semantics). Callers use it to stop a child inheriting something
      # harmful — e.g. the MudMcp preset clears BUNDLE_* so a server spawned from
      # inside `bundle exec` does not re-initialise bundler and flood stderr.
      def initialize(command:, env: {}, timeout: 60, debug: false)
        @command = command
        @env     = env.each_with_object({}) do |(key, value), out|
          out[key.to_s] = value.nil? ? nil : value.to_s
        end
        @timeout = timeout
        @debug   = debug
        @next_id = 0
        @mutex   = Mutex.new
      end

      def start
        @stdin, @stdout, @stderr, @wait = Open3.popen3(@env, *@command)
        @stdin.sync = true

        # Drain stderr continuously. A server that logs faster than we read would
        # otherwise block forever on a full pipe buffer — a classic subprocess
        # deadlock that only shows up under load.
        @stderr_thread = Thread.new do
          @stderr.each_line { |line| warn "[mcp] #{line.chomp}" if @debug }
        rescue IOError
          # pipe closed on shutdown
        end

        result = request("initialize", {
          "protocolVersion" => PROTOCOL_VERSION,
          "capabilities"    => {},
          "clientInfo"      => { "name" => "boukensha", "version" => Boukensha::VERSION }
        })

        negotiated = result["protocolVersion"]
        unless negotiated == PROTOCOL_VERSION
          warn "[mcp] server speaks #{negotiated}, we speak #{PROTOCOL_VERSION} — continuing"
        end

        @server_info  = result["serverInfo"] || {}
        @instructions = result["instructions"]

        notify("notifications/initialized")
        self
      end

      # Tool descriptors straight from the server, cached for the process.
      def tools
        @tools ||= request("tools/list")["tools"] || []
      end

      # Invoke a tool and return its text content.
      #
      # An MCP result carries isError to distinguish "the tool ran and reports a
      # problem" from "the call itself failed". We fold the former into the
      # returned string rather than raising: BOUKENSHA tools answer the agent with
      # an "error: …" message so it can correct itself, exactly as the in-process
      # MUD tools do.
      def call_tool(name, arguments = {})
        result  = request("tools/call", { "name" => name, "arguments" => arguments })
        text    = Array(result["content"]).map { |block| block["text"] }.compact.join("\n")
        text
      end

      def close
        @stdin&.close unless @stdin&.closed?   # documented MCP stdio shutdown signal
        @wait&.value                            # reap
      rescue StandardError
        nil
      ensure
        @stderr_thread&.kill
        [@stdout, @stderr].each { |io| io&.close unless io&.closed? }
      end

      def running? = !@wait.nil? && @wait.alive?

      private

      def request(method, params = nil)
        @mutex.synchronize do
          id      = (@next_id += 1)
          message = { "jsonrpc" => "2.0", "id" => id, "method" => method }
          message["params"] = params if params

          write(message)
          response = read_response(id)

          if (error = response["error"])
            raise ProtocolError, "#{method} failed (#{error['code']}): #{error['message']}"
          end

          response["result"] || {}
        end
      end

      def notify(method, params = nil)
        @mutex.synchronize do
          message = { "jsonrpc" => "2.0", "method" => method }
          message["params"] = params if params
          write(message)
        end
      end

      def write(message)
        @stdin.puts(JSON.generate(message))
      rescue Errno::EPIPE
        raise Error, "MCP server exited"
      end

      # Read until the response with our id arrives, skipping any notification
      # the server may interleave.
      def read_response(id)
        Timeout.timeout(@timeout) do
          loop do
            line = @stdout.gets
            raise Error, "MCP server closed the connection" if line.nil?
            next if line.strip.empty?

            message = begin
              JSON.parse(line)
            rescue JSON::ParserError => e
              raise ProtocolError, "malformed response: #{e.message}"
            end

            next unless message["id"] == id

            return message
          end
        end
      rescue Timeout::Error
        raise Error, "MCP server did not respond within #{@timeout}s"
      end
  end
end
end
