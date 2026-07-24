require_relative "boukensha/version"
require_relative "boukensha/config"
require_relative "boukensha/tasks/player"

module Boukensha
  @debug  = false
  @config = nil

  def self.config
    @config ||= Config.new
  end

  def self.debug!
    @debug = true
  end

  def self.debug?
    @debug
  end

  # One-shot run: send a single task, get a response, return.
  #
  # working_dir:      roots all tool calls to this directory (default: Dir.pwd).
  #                   Registers Boukensha::Tools::FileSystem (pwd, list_directory,
  #                   read_file, write_file, delete_file, search_files) and
  #                   Boukensha::Tools::Shell (run_command) automatically.
  #                   Pass working_dir: false to opt out entirely.
  #
  # allowed_commands: Array of shell-executable names the agent is allowed to
  #                   run via run_command (e.g. ["ruby", "git"]).
  #                   nil (default) permits everything — useful for demos.
  #                   Pass an empty Array [] to disable run_command entirely.
  #
  # shell_timeout:    Seconds before a run_command is killed (default 30).
  #
  # mud:              Hash of MUD connection options (host/port/name/password).
  #                   When nil (default), config.mud_* values from settings.yaml
  #                   are used. Pass mud: false to disable MUD play entirely.
  #                   With no connection settings anywhere, no MUD tools are
  #                   registered and no MCP server is started.
  #
  # mud_mcp:          Where the MUD tools come from. true (default) sources them
  #                   from the mud_manager_mcp server over MCP — the tools are
  #                   defined once there and discovered at runtime, so this is
  #                   the same tool set every language gets. Pass a Hash to add
  #                   options (command:, autoconnect:, only:, except:, debug:).
  #                   Pass false to use the in-process Tools::Mud instead, which
  #                   needs no subprocess but restates every tool by hand.
  #
  # mcp_servers:      Additional MCP servers to connect, on top of the MUD.
  #                   nil (default) reads settings.yaml's `mcp_servers:` block;
  #                   a Hash of name => spec overrides it; false connects none.
  #                   This is the config-driven path — plug in any third-party
  #                   MCP server by editing YAML, no new code.
  def self.run(
    task:,
    system:           nil,
    model:            nil,
    backend:          nil,
    api_key:          nil,
    ollama_host:      "http://localhost:11434",
    log:              nil,
    max_output_tokens: nil,
    working_dir:      Dir.pwd,
    allowed_commands: nil,
    shell_timeout:    30,
    mud:              nil,
    mud_mcp:          true,
    mcp_servers:      nil,
    &block
  )
    cfg           = config                           # loads .env; populates ENV
    task_class    = Tasks::Player
    task_settings = cfg.tasks(task_class.task_name)
    system      ||= task_class.system_prompt(task_settings, user_prompts_dir: cfg.user_prompts_dir, default_prompts_dir: Config::PROMPTS_DIR)
    model       ||= task_class.model(task_settings)
    backend     ||= task_class.provider(task_settings).to_sym
    api_key ||= case backend
                when :anthropic    then ENV["ANTHROPIC_API_KEY"]
                when :openai       then ENV["OPENAI_API_KEY"]
                when :gemini       then ENV["GEMINI_API_KEY"]
                when :mammouth     then ENV["MAMMOUTH_API_KEY"]
                when :ollama_cloud then ENV["OLLAMA_API_KEY"]
                end

    ctx      = Context.new(task: task_class, system: system, working_dir: working_dir)
    registry = Registry.new(ctx)

    if working_dir
      Tools::FileSystem.register(registry, working_dir: working_dir)
      Tools::Shell.register(registry, working_dir: working_dir,
                            timeout: shell_timeout, allowed_commands: allowed_commands)
    end

    resolved_mud, mud_provenance = register_mud_tools(registry, cfg, mud: mud, mud_mcp: mud_mcp)
    mcp_provenance = register_declared_servers(registry, cfg, mcp_servers)

    RunDSL.new(registry).instance_eval(&block) if block

    be = case backend
         when :anthropic    then Backends::Anthropic.new(api_key: api_key, model: model)
         when :openai       then Backends::OpenAI.new(api_key: api_key, model: model)
         when :gemini       then Backends::Gemini.new(api_key: api_key, model: model)
         when :mammouth     then Backends::Mammouth.new(api_key: api_key, model: model)
         when :ollama       then Backends::Ollama.new(host: ollama_host, model: model)
         when :ollama_cloud then Backends::OllamaCloud.new(api_key: api_key, model: model)
         else raise ArgumentError, "Unknown backend #{backend.inspect}. Use :anthropic, :openai, :gemini, :mammouth, :ollama, or :ollama_cloud."
         end

    builder = PromptBuilder.new(ctx, be)
    client  = Client.new(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = max_output_tokens || task_class.max_output_tokens(task_settings)
    logger  = Logger.new(log: log, snapshot: {
      task:              task_class.task_name,
      max_iterations:    effective_max_iterations,
      max_output_tokens: effective_max_output_tokens,
      model:             model,
      provider:          backend,
      mud_tools:         mud_provenance,
      mcp_servers:       mcp_provenance
    }.compact)
    agent   = Agent.new(context: ctx, registry: registry, builder: builder, client: client, logger: logger,
                        task_settings: task_settings, max_iterations: effective_max_iterations, max_output_tokens: effective_max_output_tokens)

    ctx.add_message(:user, task)
    agent.run
  ensure
    logger&.close
  end

  # Interactive REPL — see Boukensha.run for full option documentation.
  #
  # tui: true (default) wraps the REPL in a charm-ruby TUI.  Pass tui: false or
  # use the --no-tui CLI flag to fall back to the plain terminal REPL.
  def self.repl(
    system:           nil,
    model:            nil,
    backend:          nil,
    api_key:          nil,
    ollama_host:      "http://localhost:11434",
    log:              nil,
    max_output_tokens: nil,
    working_dir:      Dir.pwd,
    allowed_commands: nil,
    shell_timeout:    30,
    mud:              nil,
    mud_mcp:          true,
    mcp_servers:      nil,
    tui:              true,
    &block
  )
    cfg           = config                           # loads .env; populates ENV
    task_class    = Tasks::Player
    task_settings = cfg.tasks(task_class.task_name)
    system      ||= task_class.system_prompt(task_settings, user_prompts_dir: cfg.user_prompts_dir, default_prompts_dir: Config::PROMPTS_DIR)
    model       ||= task_class.model(task_settings)
    backend     ||= task_class.provider(task_settings).to_sym
    api_key ||= case backend
                when :anthropic    then ENV["ANTHROPIC_API_KEY"]
                when :openai       then ENV["OPENAI_API_KEY"]
                when :gemini       then ENV["GEMINI_API_KEY"]
                when :mammouth     then ENV["MAMMOUTH_API_KEY"]
                when :ollama_cloud then ENV["OLLAMA_API_KEY"]
                end

    ctx      = Context.new(task: task_class, system: system, working_dir: working_dir)
    registry = Registry.new(ctx)

    if working_dir
      Tools::FileSystem.register(registry, working_dir: working_dir)
      Tools::Shell.register(registry, working_dir: working_dir,
                            timeout: shell_timeout, allowed_commands: allowed_commands)
    end

    resolved_mud, mud_provenance = register_mud_tools(registry, cfg, mud: mud, mud_mcp: mud_mcp)
    mcp_provenance = register_declared_servers(registry, cfg, mcp_servers)

    RunDSL.new(registry).instance_eval(&block) if block

    be = case backend
         when :anthropic    then Backends::Anthropic.new(api_key: api_key, model: model)
         when :openai       then Backends::OpenAI.new(api_key: api_key, model: model)
         when :gemini       then Backends::Gemini.new(api_key: api_key, model: model)
         when :mammouth     then Backends::Mammouth.new(api_key: api_key, model: model)
         when :ollama       then Backends::Ollama.new(host: ollama_host, model: model)
         when :ollama_cloud then Backends::OllamaCloud.new(api_key: api_key, model: model)
         else raise ArgumentError, "Unknown backend #{backend.inspect}. Use :anthropic, :openai, :gemini, :mammouth, :ollama, or :ollama_cloud."
         end

    builder = PromptBuilder.new(ctx, be)
    client  = Client.new(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = max_output_tokens || task_class.max_output_tokens(task_settings)
    logger  = Logger.new(log: log, snapshot: {
      task:              task_class.task_name,
      max_iterations:    effective_max_iterations,
      max_output_tokens: effective_max_output_tokens,
      model:             model,
      provider:          backend,
      mud_tools:         mud_provenance,
      mcp_servers:       mcp_provenance
    }.compact)

    repl = Repl.new(
      context:    ctx,
      registry:   registry,
      builder:    builder,
      client:     client,
      logger:     logger,
      task_settings: task_settings,
      max_iterations:    effective_max_iterations,
      max_output_tokens: effective_max_output_tokens,
      config_dir: cfg.dir,
      provider:   backend,
      model:      model,
      version:    VERSION,
      api_key:    api_key,
      mud:        resolved_mud
    )

    if tui && defined?(Tui)
      Tui.new(repl).start
    else
      repl.start
    end
  rescue Interrupt
    puts "\nInterrupted."
  ensure
    logger&.close
  end

  # Register the MUD gameplay tools, either in-process or via the MCP server.
  #
  # Both paths register tools under the same names (look, move, attack, …), so
  # they are mutually exclusive — mud_mcp wins when both are requested.
  # Returns the resolved connection settings, which the REPL banner uses to
  # show MUD reachability.
  # Returns [connection, provenance] — the latter recorded in the session log so
  # it is afterwards visible *which* implementation served the MUD tools. The
  # tool names differ between the two paths, but relying on that to tell them
  # apart is guesswork; this states it.
  def self.register_mud_tools(registry, cfg, mud:, mud_mcp:)
    return [nil, nil] if mud == false                # explicit opt-out wins

    # A Hash in mud: is a connection override; otherwise fall back to config.
    # No connection settings anywhere means no MUD tools at all — which also
    # keeps us from spawning an MCP server for an agent that will never play.
    connection = (mud.is_a?(Hash) ? mud : nil) || mud_opts_from_config(cfg)
    return [nil, nil] if connection.nil?

    if mud_mcp
      overrides = mud_mcp.is_a?(Hash) ? mud_mcp : {}
      client    = Tools::MudMcp.register(registry, **connection.merge(overrides))
      [connection, {
        source:         "mcp",
        server:         client.server_info["name"],
        server_version: client.server_info["version"]
      }.compact]
    else
      Tools::Mud.register(registry, **connection)
      [connection, { source: "in_process" }]
    end
  end
  private_class_method :register_mud_tools

  # Connect any MCP servers declared in settings.yaml's `mcp_servers:` block (or
  # passed explicitly as a Hash), on top of the MUD. This is the config-driven
  # path: a user plugs in a Kubernetes or filesystem server by editing YAML, with
  # no new code. Tool-name collisions across servers are namespaced by
  # MCP::Servers; the MUD's tools take part in that too.
  #
  #   mcp_servers: nil    -> use settings.yaml's mcp_servers block (the default)
  #   mcp_servers: {...}  -> use this Hash instead
  #   mcp_servers: false  -> connect none, even if declared in settings.yaml
  #
  # Returns the per-server provenance (recorded in the session log) or nil.
  def self.register_declared_servers(registry, cfg, mcp_servers)
    return nil if mcp_servers == false

    specs = mcp_servers.is_a?(Hash) ? mcp_servers : cfg.mcp_servers
    return nil if specs.nil? || specs.empty?

    _clients, provenance = Tools::Mcp.connect(registry, specs)
    provenance
  end
  private_class_method :register_declared_servers

  # Build a mud options hash from config (used when mud: nil is passed to run/repl).
  # Returns nil if no MUD host is configured.
  def self.mud_opts_from_config(cfg)
    return nil unless cfg.mud_host && cfg.mud_username

    {
      host:     cfg.mud_host,
      port:     cfg.mud_port,
      name:     cfg.mud_username,
      password: cfg.mud_password
    }
  end
  private_class_method :mud_opts_from_config
end

require_relative "boukensha/tool"
require_relative "boukensha/message"
require_relative "boukensha/context"
require_relative "boukensha/errors"
require_relative "boukensha/registry"
require_relative "boukensha/prompt_builder"
require_relative "boukensha/logger"
require_relative "boukensha/backends/base"
require_relative "boukensha/backends/anthropic"
require_relative "boukensha/backends/gemini"
require_relative "boukensha/backends/mammouth"
require_relative "boukensha/backends/ollama"
require_relative "boukensha/backends/ollama_cloud"
require_relative "boukensha/backends/openai"
require_relative "boukensha/client"
require_relative "boukensha/agent"
require_relative "boukensha/run_dsl"
require_relative "boukensha/repl"
require_relative "boukensha/tools/file_system"
require_relative "boukensha/tools/shell"
require_relative "boukensha/tools/mud"
require_relative "boukensha/mcp"
require_relative "boukensha/tools/mcp"
require_relative "boukensha/tools/mud_mcp"
require_relative "boukensha/tui"
