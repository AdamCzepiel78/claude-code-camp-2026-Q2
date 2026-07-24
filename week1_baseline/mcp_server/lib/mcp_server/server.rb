require "json"

module McpServer
  # A Model Context Protocol server speaking JSON-RPC 2.0 over stdio.
  #
  # There is nothing domain-specific here — no MUD, no filesystem, no database.
  # Everything that makes a server *that* server is injected: its identity, its
  # instructions, its tools, and what to do on shutdown. Point it at a tool
  # provider and it is a working MCP server.
  #
  # Hand-rolled rather than pulling in an SDK, for the same reason the rest of
  # this bootcamp avoids dependencies: the wire protocol is small enough to read
  # in one sitting, and keeping it visible is the point. One JSON object per
  # line in on stdin, one per line out on stdout.
  #
  # STDOUT IS THE PROTOCOL. Nothing may write to it but this class — that is why
  # every diagnostic goes to stderr, and why a tool provider must use `warn`
  # rather than `puts` for its own output.
  #
  #   McpServer::Server.new(
  #     tools:        MyTools,                  # see the tool-provider contract below
  #     name:         "my-server",
  #     version:      "1.0.0",
  #     instructions: "Call setup_thing first.",
  #     on_shutdown:  -> { cleanup }
  #   ).run
  #
  # ## Tool-provider contract
  #
  # `tools:` is any object answering two methods:
  #
  #   #descriptors        -> Array of {"name" =>, "description" =>, "inputSchema" =>}
  #   #call(name, args)   -> [text, is_error]
  #
  # `call` should return `[message, true]` for problems the caller could fix —
  # a bad argument, a missing precondition — so the agent reads the message and
  # corrects itself. Raise KeyError only for a genuinely unknown tool name; that
  # becomes a JSON-RPC error rather than a tool result.
  class Server
    PROTOCOL_VERSION = "2025-06-18".freeze

    # JSON-RPC 2.0 error codes.
    PARSE_ERROR      = -32_700
    INVALID_REQUEST  = -32_600
    METHOD_NOT_FOUND = -32_601
    INVALID_PARAMS   = -32_602
    INTERNAL_ERROR   = -32_603

    # Raised internally to produce a JSON-RPC error response.
    class RpcError < StandardError
      attr_reader :code

      def initialize(code, message)
        super(message)
        @code = code
      end
    end

    # on_shutdown: called once when stdin closes — release whatever the tools
    #              hold open (connections, files, child processes). Optional.
    def initialize(tools:, name:, version:,
                   instructions: nil, on_shutdown: nil,
                   input: $stdin, output: $stdout, debug: false)
      @tools        = tools
      @name         = name
      @version      = version
      @instructions = instructions
      @on_shutdown  = on_shutdown
      @in           = input
      @out          = output
      @debug        = debug
    end

    def run
      @out.sync = true
      log "listening on stdio (protocol #{PROTOCOL_VERSION})"

      while (line = @in.gets)
        line = line.strip
        next if line.empty?

        process(line)
      end

      log "stdin closed, shutting down"
    ensure
      # The client closing stdin is MCP's documented shutdown signal for stdio
      # transports — this is where a server releases what it was holding.
      @on_shutdown&.call
    end

    private

    def process(line)
      begin
        message = JSON.parse(line)
      rescue JSON::ParserError => e
        return respond(nil, error: [PARSE_ERROR, "invalid JSON: #{e.message}"])
      end

      unless message.is_a?(Hash)
        return respond(nil, error: [INVALID_REQUEST, "request must be a JSON object"])
      end

      # A message without an "id" is a notification: handle it, answer nothing.
      # Replying to one is a protocol violation, not a harmless extra.
      unless message.key?("id")
        handle_notification(message["method"])
        return
      end

      id = message["id"]
      begin
        respond(id, result: dispatch(message["method"], message["params"] || {}))
      rescue RpcError => e
        respond(id, error: [e.code, e.message])
      rescue StandardError => e
        log "unhandled: #{e.class}: #{e.message}"
        respond(id, error: [INTERNAL_ERROR, "#{e.class}: #{e.message}"])
      end
    end

    def handle_notification(method)
      log "notification: #{method}"
      # notifications/initialized is the only one we expect; nothing to do.
    end

    def dispatch(method, params)
      case method
      when "initialize" then handshake(params)
      when "ping"       then {}
      when "tools/list" then { "tools" => @tools.descriptors }
      when "tools/call" then call_tool(params)
      else
        raise RpcError.new(METHOD_NOT_FOUND, "unknown method: #{method}")
      end
    end

    def handshake(params)
      log "client #{params.dig('clientInfo', 'name') || 'unknown'} " \
          "requested #{params['protocolVersion']}"

      # Spec: echo the client's version when we support it, otherwise reply with
      # the newest we do support and let the client decide.
      payload = {
        "protocolVersion" => PROTOCOL_VERSION,
        "capabilities"    => { "tools" => { "listChanged" => false } },
        "serverInfo"      => { "name" => @name, "version" => @version }
      }

      # `instructions` is the protocol's channel for "here is how to drive me" —
      # which tool to call first, what state this server holds. A client can fold
      # it into the agent's prompt, so a stateful server explains its own
      # lifecycle instead of every client hard-coding it.
      payload["instructions"] = @instructions if @instructions

      payload
    end

    def call_tool(params)
      name = params["name"]
      raise RpcError.new(INVALID_PARAMS, "missing tool name") if name.nil?

      begin
        text, is_error = @tools.call(name, params["arguments"] || {})
      rescue KeyError => e
        raise RpcError.new(INVALID_PARAMS, e.message)
      end

      { "content" => [{ "type" => "text", "text" => text.to_s }], "isError" => !!is_error }
    end

    def respond(id, result: nil, error: nil)
      payload = { "jsonrpc" => "2.0", "id" => id }
      if error
        code, message = error
        payload["error"] = { "code" => code, "message" => message }
      else
        payload["result"] = result
      end

      @out.puts(JSON.generate(payload))
    end

    def log(message)
      warn "[mcp_server:#{@name}] #{message}" if @debug
    end
  end
end
