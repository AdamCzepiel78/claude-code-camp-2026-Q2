require "json"

require_relative "session_registry"
require_relative "tools"

module MudManagerMcp
  # A Model Context Protocol server speaking JSON-RPC 2.0 over stdio.
  #
  # Hand-rolled rather than pulling in an MCP SDK, for the same reason
  # mud_manager itself has no dependencies: the wire protocol is small enough
  # to read in one sitting, and keeping it visible is the point. One JSON
  # object per line in on stdin, one per line out on stdout.
  #
  # STDOUT IS THE PROTOCOL. Nothing may write to it but this class — that is
  # why every diagnostic here goes to stderr, and why MudManagerMcp::Session uses
  # `warn` rather than `puts` for its own warnings.
  class Server
    PROTOCOL_VERSION = "2025-06-18".freeze
    SERVER_NAME      = "mud-manager".freeze
    SERVER_VERSION   = "0.1.0".freeze

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

    def initialize(registry:, input: $stdin, output: $stdout, debug: false)
      @registry = registry
      @in       = input
      @out      = output
      @debug    = debug
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
      # Close MUD connections on the way out so characters are not left
      # linkdead. The client closing stdin is MCP's documented shutdown
      # signal for stdio transports.
      @registry.close_all
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
      when "tools/list" then { "tools" => Tools.descriptors }
      when "tools/call" then call_tool(params)
      else
        raise RpcError.new(METHOD_NOT_FOUND, "unknown method: #{method}")
      end
    end

    def handshake(params)
      requested = params["protocolVersion"]
      log "client #{params.dig('clientInfo', 'name') || 'unknown'} requested #{requested}"

      # Spec: echo the client's version when we support it, otherwise reply
      # with the newest we do support and let the client decide.
      {
        "protocolVersion" => PROTOCOL_VERSION,
        "capabilities"    => { "tools" => { "listChanged" => false } },
        "serverInfo"      => { "name" => SERVER_NAME, "version" => SERVER_VERSION },
        "instructions"    => instructions
      }
    end

    def instructions
      "Drives a CircleMUD/tbaMUD character over a live telnet session.\n" \
        "Call session_open once before any gameplay tool — logging in takes about " \
        "six seconds, and the session is then reused for every later call.\n" \
        "Pass session_id to run several characters at once; omit it for 'default'.\n" \
        "The MUD also emits output nobody asked for (combat rounds, arriving mobs, " \
        "channel chatter). Use read_until_quiet or drain to collect it."
    end

    def call_tool(params)
      name = params["name"]
      raise RpcError.new(INVALID_PARAMS, "missing tool name") if name.nil?

      begin
        text, is_error = Tools.call(name, params["arguments"], registry: @registry)
      rescue KeyError => e
        raise RpcError.new(INVALID_PARAMS, e.message)
      end

      { "content" => [{ "type" => "text", "text" => text }], "isError" => is_error }
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
      warn "[mud_manager.mcp] #{message}" if @debug
    end
  end
end
