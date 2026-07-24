module McpServer
  # A small builder for the tool-provider contract McpServer::Server expects.
  #
  # Using it is optional — any object answering #descriptors and #call works —
  # but it removes the boilerplate of hand-assembling JSON Schema and dispatch:
  #
  #   tools = McpServer::ToolTable.new(rescuable: [ValueError])
  #   tools.add("note_add", "Append a note.",
  #             { "text" => { "type" => "string", "description" => "The note" } },
  #             required: ["text"]) { |args| store << args["text"]; "added" }
  #
  # `rescuable:` names the exceptions a *caller* could plausibly fix — a bad
  # enum value, a missing precondition. Those come back as `isError` tool
  # results carrying the message, so the agent reads it and corrects itself.
  # Anything else propagates and becomes a JSON-RPC internal error, because a
  # bug in the server is not something the agent can work around.
  class ToolTable
    Tool = Struct.new(:name, :description, :schema, :handler, keyword_init: true)

    def initialize(rescuable: [ArgumentError])
      @tools     = {}
      @rescuable = Array(rescuable)
    end

    # properties: JSON Schema `properties` for this tool's arguments.
    # required:   which of those are mandatory.
    # The block receives the arguments hash (string keys) and returns the text
    # the agent should see.
    def add(name, description, properties = {}, required: [], &handler)
      raise ArgumentError, "tool #{name} needs a handler block" if handler.nil?

      @tools[name.to_s] = Tool.new(
        name:        name.to_s,
        description: description,
        schema:      {
          "type"       => "object",
          "properties" => properties,
          "required"   => required
        },
        handler:     handler
      )
      self
    end

    def names = @tools.keys

    # ---- the tool-provider contract ----

    def descriptors
      @tools.values.map do |tool|
        { "name" => tool.name, "description" => tool.description, "inputSchema" => tool.schema }
      end
    end

    # Returns [text, is_error]. Raises KeyError for an unknown tool so the
    # server can report it as a protocol error rather than a tool result.
    def call(name, args = {})
      tool = @tools[name.to_s]
      raise KeyError, "unknown tool: #{name}" if tool.nil?

      [tool.handler.call(args || {}).to_s, false]
    rescue *@rescuable => e
      ["error: #{e.message}", true]
    end
  end
end
