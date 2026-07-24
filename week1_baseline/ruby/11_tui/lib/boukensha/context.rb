require_relative "tool"
require_relative "message"

module Boukensha
  class Context
    attr_reader :task, :system, :messages, :tools, :working_dir

    # Append text to the system prompt after construction.
    #
    # Used by Tools::Mcp to fold an MCP server's `instructions` into the prompt.
    # The server declares how it wants to be driven — which tool to call first,
    # what state it holds — and the agent reads that, instead of the client
    # hard-coding knowledge of a particular server's tools.
    def append_system(text)
      return if text.nil? || text.to_s.strip.empty?

      parts   = [@system, text].compact.reject { |s| s.to_s.strip.empty? }
      @system = parts.join("\n\n")
    end

    def initialize(task:, system: nil, working_dir: nil)
      @task        = task
      @system      = system
      @working_dir  = working_dir ? File.expand_path(working_dir) : nil
      @messages     = []
      @tools        = {}
    end

    def register_tool(tool)
      @tools[tool.name] = tool
    end

    def add_message(role, content, tool_use_id: nil)
      @messages << Message.new(role, content, tool_use_id)
    end

    # Drop all conversation history, keeping tools and system prompt intact.
    # Used by the REPL's `clear` command.
    def clear_messages!
      @messages = []
    end

    def tool_count = @tools.size
    def turn_count = @messages.size

    def to_s
      "#<Context task=#{task&.task_name} turns=#{turn_count} tools=#{tool_count}>"
    end
  end
end
