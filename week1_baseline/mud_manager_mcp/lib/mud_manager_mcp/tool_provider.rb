require_relative "tools"

module MudManagerMcp
  # Binds the MUD tool table to a SessionRegistry so it satisfies the
  # tool-provider contract McpServer::Server expects (#descriptors and
  # #call(name, args)).
  #
  # This exists because the tools are stateful — every gameplay call needs the
  # registry that owns the live telnet sessions — while the transport is
  # deliberately stateless and knows nothing about them. Binding here is what
  # lets the generic server stay generic.
  class ToolProvider
    def initialize(registry)
      @registry = registry
    end

    def descriptors = Tools.descriptors

    def call(name, args = {})
      Tools.call(name, args, registry: @registry)
    end
  end
end
