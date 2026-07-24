require_relative "session"

module MudManagerMcp
  # Holds every live MudManagerMcp::Session, keyed by a caller-chosen id.
  #
  # This is the piece that makes MCP viable for a MUD at all. Logging in costs
  # ~5.9s against a real CircleMUD server, while a command on an already-open
  # session costs ~0.1s — a 61x difference. The MCP server process therefore
  # stays alive and keeps sessions warm across tool calls, instead of
  # connecting per request.
  #
  # Multi-session means one server process can drive several characters at
  # once (e.g. a fighter and a healer), each addressed by its own session_id.
  #
  # IMPORTANT — a session is single-consumer. Session#drain is destructive:
  # whoever reads first empties the buffer. Two clients sharing one session_id
  # will steal each other's output. Give each consumer its own session_id.
  class SessionRegistry
    class UnknownSession < StandardError; end
    class DuplicateSession < StandardError; end

    DEFAULT_ID = "default".freeze

    def initialize(defaults: {})
      @defaults = defaults
      @sessions = {}
      @mutex    = Mutex.new
    end

    # Connection settings used when a tool call omits them. Sourced from the
    # process environment / CLI flags so `session_open` can be called bare.
    attr_reader :defaults

    def open(id: DEFAULT_ID, host: nil, port: nil, name: nil, password: nil)
      host     ||= @defaults[:host]
      port     ||= @defaults[:port]
      name     ||= @defaults[:name]
      password ||= @defaults[:password]

      raise ArgumentError, "no character name given and no default configured" if blank?(name)
      raise ArgumentError, "no password given and no default configured"       if blank?(password)

      @mutex.synchronize do
        existing = @sessions[id]
        raise DuplicateSession, "session '#{id}' is already open" if existing&.open?

        session = Session.new(host: host, port: port)
        session.open
        session.login(name, password)
        @sessions[id] = session
        Entry.new(id: id, session: session, character: name)
      end
    end

    # Fetch an open session, or raise. Callers surface the error as tool text
    # so the agent can decide to call session_open itself.
    def fetch(id = DEFAULT_ID)
      session = @mutex.synchronize { @sessions[id] }
      raise UnknownSession, "no session '#{id}' — call session_open first" if session.nil?
      raise UnknownSession, "session '#{id}' is closed — call session_open first" unless session.open?

      session
    end

    def close(id = DEFAULT_ID)
      @mutex.synchronize do
        session = @sessions.delete(id)
        raise UnknownSession, "no session '#{id}'" if session.nil?

        session.close
        id
      end
    end

    def list
      @mutex.synchronize do
        @sessions.map do |id, session|
          { "session_id" => id, "host" => session.host, "port" => session.port,
            "open" => session.open? }
        end
      end
    end

    def open?(id = DEFAULT_ID)
      session = @mutex.synchronize { @sessions[id] }
      !session.nil? && session.open?
    end

    # Best-effort cleanup on server shutdown so characters are not left
    # linkdead on the MUD.
    def close_all
      @mutex.synchronize do
        @sessions.each_value do |session|
          begin
            session.close
          rescue StandardError
            # shutting down anyway
          end
        end
        @sessions.clear
      end
    end

    Entry = Struct.new(:id, :session, :character, keyword_init: true)

    private

    def blank?(value) = value.nil? || value.to_s.strip.empty?
  end
end
