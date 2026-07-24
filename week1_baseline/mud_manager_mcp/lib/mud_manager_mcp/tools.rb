require_relative "primitives"
require_relative "session_registry"

module MudManagerMcp
  # The tool surface exposed over MCP, defined declaratively.
  #
  # Three groups:
  #   session_*        — lifecycle: open/close/list/status (multi-session)
  #   send_raw, read_* — the low-level primitives
  #   everything else  — typed gameplay verbs built on MudManagerMcp::Primitives
  #
  # The read primitives are deliberately first-class rather than hidden behind
  # "send a command, get a response". A MUD pushes output the client never
  # asked for (combat rounds, mobs arriving, channel chatter), so a caller
  # needs a way to collect that without sending anything.
  module Tools
    Tool = Struct.new(:name, :description, :schema, :handler, keyword_init: true)

    SESSION_ID_PROPERTY = {
      "session_id" => {
        "type" => "string",
        "description" => "Which MUD session to act on. Defaults to 'default'. " \
                         "Use session_list to see what is open."
      }
    }.freeze

    module_function

    def schema(properties = {}, required: [])
      {
        "type"       => "object",
        "properties" => SESSION_ID_PROPERTY.merge(properties),
        "required"   => required
      }
    end

    def str(description)  = { "type" => "string",  "description" => description }
    def int(description)  = { "type" => "integer", "description" => description }
    def num(description)  = { "type" => "number",  "description" => description }

    def session_id(args) = args["session_id"] || SessionRegistry::DEFAULT_ID

    # Shared gameplay path: resolve the session, build the command, then drain
    # stale bytes before sending so read_until_prompt sees only this command's
    # output. Mirrors the send_cmd lambda in boukensha's tools/mud.rb.
    def play(registry, args)
      session = registry.fetch(session_id(args))
      command = yield
      session.drain
      session.send_command(command)
      session.read_until_prompt
    end

    P = MudManagerMcp::Primitives

    # ---------------------------------------------------------------- table

    def all
      @all ||= [
        # ── Session lifecycle ───────────────────────────────────────────
        Tool.new(
          name: "session_open",
          description: "Open a MUD connection and log a character in, then keep it alive for " \
                       "subsequent tool calls. Logging in is slow (~6s), so do it once and reuse " \
                       "the session. Omitted settings fall back to the server's configured " \
                       "defaults. Use a distinct session_id to drive several characters at once.",
          schema: schema({
            "host"     => str("MUD host (default: server's configured host)"),
            "port"     => int("MUD port (default: server's configured port)"),
            "name"     => str("Character name (default: server's configured character)"),
            "password" => str("Character password (default: server's configured password)")
          }),
          handler: lambda do |registry, args|
            entry = registry.open(
              id: session_id(args), host: args["host"], port: args["port"],
              name: args["name"], password: args["password"]
            )
            "session '#{entry.id}' open as #{entry.character} on " \
              "#{entry.session.host}:#{entry.session.port}"
          end
        ),

        Tool.new(
          name: "session_close",
          description: "Close a MUD session and release its connection.",
          schema: schema,
          handler: ->(registry, args) { "session '#{registry.close(session_id(args))}' closed" }
        ),

        Tool.new(
          name: "session_list",
          description: "List every MUD session this server currently holds, with its host, " \
                       "port, and whether it is still connected.",
          schema: { "type" => "object", "properties" => {} },
          handler: lambda do |registry, _args|
            rows = registry.list
            next "no sessions open" if rows.empty?

            rows.map { |r|
              "#{r['session_id']}: #{r['host']}:#{r['port']} " \
                "(#{r['open'] ? 'connected' : 'disconnected'})"
            }.join("\n")
          end
        ),

        Tool.new(
          name: "session_status",
          description: "Report whether one specific MUD session is currently connected.",
          schema: schema,
          handler: lambda do |registry, args|
            id = session_id(args)
            registry.open?(id) ? "session '#{id}' is connected" : "session '#{id}' is not connected"
          end
        ),

        # ── Low-level primitives ────────────────────────────────────────
        Tool.new(
          name: "send_raw",
          description: "Send an arbitrary command string to the MUD and return its response. " \
                       "Escape hatch for when no typed tool fits (e.g. 'who', 'help backstab').",
          schema: schema({ "command" => str("The raw command line to send") },
                         required: ["command"]),
          handler: lambda do |registry, args|
            session = registry.fetch(session_id(args))
            session.drain
            session.send_command(args["command"])
            session.read_until_quiet
          end
        ),

        Tool.new(
          name: "read_until_prompt",
          description: "Read buffered MUD output up to the next command prompt, without sending " \
                       "anything. Use to collect output that arrived on its own.",
          schema: schema({ "timeout" => num("Seconds to wait before giving up (default 10)") }),
          handler: lambda do |registry, args|
            out = registry.fetch(session_id(args)).read_until_prompt(timeout: args["timeout"])
            out.to_s.empty? ? "(nothing buffered)" : out
          end
        ),

        Tool.new(
          name: "read_until_quiet",
          description: "Read MUD output until the server has been silent for a while, without " \
                       "sending anything. Best way to collect unprompted output such as combat " \
                       "rounds, arriving mobs, or channel chatter.",
          schema: schema({
            "quiet_seconds" => num("Silence window that ends the read (default 1.0)"),
            "timeout"       => num("Total seconds to wait before giving up (default 10)")
          }),
          handler: lambda do |registry, args|
            session = registry.fetch(session_id(args))
            out = session.read_until_quiet(args["quiet_seconds"] || 1.0, timeout: args["timeout"])
            out.to_s.empty? ? "(nothing buffered)" : out
          end
        ),

        Tool.new(
          name: "drain",
          description: "Immediately return whatever output is already buffered, without waiting " \
                       "and without sending anything. Non-blocking. Note this empties the buffer.",
          schema: schema,
          handler: lambda do |registry, args|
            out = registry.fetch(session_id(args)).drain
            out.to_s.empty? ? "(nothing buffered)" : out
          end
        ),

        # ── Perception ──────────────────────────────────────────────────
        Tool.new(
          name: "look",
          description: "Look at the current room or at a specific target. Call with NO arguments " \
                       "to describe the current room (do NOT pass target: 'room'). Pass a target " \
                       "to inspect an item, mob, or player. Use preposition 'in' to look inside a " \
                       "container, 'at' to inspect, or a direction to peek into an adjacent room.",
          schema: schema({
            "target"      => str("Item, mob, or player to inspect. Omit to describe the room."),
            "preposition" => str("in, at, north, east, south, west, up, down (optional)")
          }),
          handler: lambda do |registry, args|
            play(registry, args) { P.look(target: args["target"], preposition: args["preposition"]) }
          end
        ),

        Tool.new(
          name: "examine",
          description: "Examine a target in detail (more verbose than look).",
          schema: schema({ "target" => str("The item, mob, or player to examine") },
                         required: ["target"]),
          handler: ->(registry, args) { play(registry, args) { P.examine(args["target"]) } }
        ),

        Tool.new(
          name: "check",
          description: "Query information about your character or surroundings.",
          schema: schema({
            "kind" => str("score | inventory | equipment | gold | exits | time | weather | " \
                          "levels | wimpy | toggle | where")
          }, required: ["kind"]),
          handler: ->(registry, args) { play(registry, args) { P.info_self(args["kind"]) } }
        ),

        # ── Movement ────────────────────────────────────────────────────
        Tool.new(
          name: "move",
          description: "Move in a compass direction or up/down.",
          schema: schema({ "direction" => str("north | east | south | west | up | down") },
                         required: ["direction"]),
          handler: ->(registry, args) { play(registry, args) { P.move(args["direction"]) } }
        ),

        Tool.new(
          name: "flee",
          description: "Attempt to flee from combat in a random available direction.",
          schema: schema,
          handler: ->(registry, args) { play(registry, args) { P.flee } }
        ),

        Tool.new(
          name: "set_position",
          description: "Change body position. Use 'rest' or 'sleep' between fights to recover HP " \
                       "and mana. You must be standing to move or fight.",
          schema: schema({ "position" => str("stand | sit | rest | sleep | wake") },
                         required: ["position"]),
          handler: ->(registry, args) { play(registry, args) { P.set_position(args["position"]) } }
        ),

        Tool.new(
          name: "track",
          description: "Track a mob or player by name to reveal which direction they are in. " \
                       "Requires the Track skill.",
          schema: schema({ "target" => str("Name of the mob or player to track") },
                         required: ["target"]),
          handler: ->(registry, args) { play(registry, args) { P.track(args["target"]) } }
        ),

        # ── Combat ──────────────────────────────────────────────────────
        Tool.new(
          name: "attack",
          description: "Attack a target. 'kill' is the standard approach; 'murder' bypasses the " \
                       "mercy check; 'hit' is a one-off strike.",
          schema: schema({
            "target" => str("Name of the mob or player to attack"),
            "style"  => str("kill | hit | murder (default: kill)")
          }, required: ["target"]),
          handler: lambda do |registry, args|
            play(registry, args) { P.attack(args["style"] || "kill", args["target"]) }
          end
        ),

        Tool.new(
          name: "skill_strike",
          description: "Use a combat skill against a target.",
          schema: schema({
            "skill"  => str("bash | kick | backstab | rescue | assist"),
            "target" => str("Name of the mob or player")
          }, required: %w[skill target]),
          handler: lambda do |registry, args|
            play(registry, args) { P.skill_strike(args["skill"], args["target"]) }
          end
        ),

        Tool.new(
          name: "consider",
          description: "Assess a mob's relative strength before engaging. Returns a phrase such " \
                       "as 'You could kill it easily' or 'Death awaits you'. Always consider " \
                       "before attacking an unknown mob.",
          schema: schema({ "target" => str("Name of the mob to consider") }, required: ["target"]),
          handler: ->(registry, args) { play(registry, args) { P.consider(args["target"]) } }
        ),

        # ── Communication ───────────────────────────────────────────────
        Tool.new(
          name: "say",
          description: "Speak or emote in the current room.",
          schema: schema({
            "text" => str("What to say or emote"),
            "mode" => str("say | emote | reply (default: say)")
          }, required: ["text"]),
          handler: lambda do |registry, args|
            play(registry, args) { P.say_local(args["mode"] || "say", args["text"]) }
          end
        ),

        Tool.new(
          name: "tell",
          description: "Send a private message to a specific player.",
          schema: schema({
            "target" => str("Player name to message"),
            "text"   => str("The message"),
            "mode"   => str("tell | whisper | ask (default: tell)")
          }, required: %w[target text]),
          handler: lambda do |registry, args|
            play(registry, args) { P.say_targeted(args["mode"] || "tell", args["target"], args["text"]) }
          end
        ),

        Tool.new(
          name: "channel_say",
          description: "Broadcast a message over a global channel.",
          schema: schema({
            "channel" => str("shout | gossip | auction | grats | holler"),
            "text"    => str("The message to broadcast")
          }, required: %w[channel text]),
          handler: lambda do |registry, args|
            play(registry, args) { P.say_channel(args["channel"], args["text"]) }
          end
        ),

        # ── Inventory & equipment ───────────────────────────────────────
        Tool.new(
          name: "get_item",
          description: "Pick up an item from the room or from a container.",
          schema: schema({
            "item"      => str("Name of the item to get"),
            "container" => str("Container to take it from (optional)"),
            "count"     => int("How many to take (optional)")
          }, required: ["item"]),
          handler: lambda do |registry, args|
            play(registry, args) { P.get(args["item"], container: args["container"], count: args["count"]) }
          end
        ),

        Tool.new(
          name: "drop_item",
          description: "Drop, donate, or junk an item.",
          schema: schema({
            "item"  => str("Name of the item"),
            "mode"  => str("drop | donate | junk (default: drop)"),
            "count" => int("How many (optional)")
          }, required: ["item"]),
          handler: lambda do |registry, args|
            play(registry, args) { P.drop(args["mode"] || "drop", args["item"], count: args["count"]) }
          end
        ),

        Tool.new(
          name: "put_item",
          description: "Put an item into a container.",
          schema: schema({
            "item"      => str("Name of the item to put"),
            "container" => str("Name of the container"),
            "count"     => int("How many (optional)")
          }, required: %w[item container]),
          handler: lambda do |registry, args|
            play(registry, args) { P.put(args["item"], args["container"], count: args["count"]) }
          end
        ),

        Tool.new(
          name: "equip_item",
          description: "Wear, wield, hold, grab, or remove an item.",
          schema: schema({
            "item"     => str("Name of the item"),
            "action"   => str("wear | wield | hold | grab | remove"),
            "body_loc" => str("Body location, e.g. 'head', 'finger' (optional)")
          }, required: %w[item action]),
          handler: lambda do |registry, args|
            play(registry, args) { P.equip(args["action"], args["item"], body_loc: args["body_loc"]) }
          end
        ),

        Tool.new(
          name: "consume_item",
          description: "Eat, drink, taste, or sip a consumable item.",
          schema: schema({
            "item" => str("Name of the item to consume"),
            "mode" => str("eat | drink | taste | sip (default: eat)")
          }, required: ["item"]),
          handler: lambda do |registry, args|
            play(registry, args) { P.consume(args["mode"] || "eat", args["item"]) }
          end
        ),

        # ── Magic ───────────────────────────────────────────────────────
        Tool.new(
          name: "cast_spell",
          description: "Cast a spell, optionally at a target.",
          schema: schema({
            "spell"  => str("Full spell name, e.g. 'cure light wounds'"),
            "target" => str("Target mob, player, or object (optional)")
          }, required: ["spell"]),
          handler: lambda do |registry, args|
            play(registry, args) { P.cast(args["spell"], target: args["target"]) }
          end
        ),

        Tool.new(
          name: "use_magic_item",
          description: "Activate a magic item: quaff a potion, recite a scroll, or use a wand/staff.",
          schema: schema({
            "item"        => str("Name of the item to activate"),
            "mode"        => str("quaff | recite | use"),
            "target_args" => str("Optional target arguments, e.g. a mob name for a wand")
          }, required: %w[item mode]),
          handler: lambda do |registry, args|
            play(registry, args) do
              P.use_magic_item(args["mode"], args["item"], target_args: args["target_args"])
            end
          end
        ),

        # ── Utility ─────────────────────────────────────────────────────
        Tool.new(
          name: "shop",
          description: "Interact with a shop NPC: list stock, buy, sell, or value an item.",
          schema: schema({
            "action" => str("list | buy | sell | value | offer"),
            "args"   => str("Item name or number (optional)")
          }, required: ["action"]),
          handler: lambda do |registry, args|
            play(registry, args) { P.shop(args["action"], args: args["args"]) }
          end
        ),

        Tool.new(
          name: "practice",
          description: "List your known skills at a guildmaster, or practice a specific skill.",
          schema: schema({ "skill" => str("Skill to practice (omit to list all)") }),
          handler: ->(registry, args) { play(registry, args) { P.practice(args["skill"]) } }
        ),

        Tool.new(
          name: "save_character",
          description: "Save your character to disk so progress survives a disconnect.",
          schema: schema,
          handler: ->(registry, args) { play(registry, args) { P.save_char } }
        )
      ].freeze
    end

    def find(name) = all.find { |t| t.name == name }

    # MCP tools/list payload.
    def descriptors
      all.map do |tool|
        { "name" => tool.name, "description" => tool.description, "inputSchema" => tool.schema }
      end
    end

    # Invoke a tool. Returns [text, is_error].
    #
    # Everything the caller could plausibly get wrong — unknown session, bad
    # enum value, dropped connection — comes back as isError text rather than
    # a JSON-RPC error, so an agent can read the message and correct itself.
    # Only an unknown tool name is a protocol-level error (raised to caller).
    def call(name, args, registry:)
      tool = find(name)
      raise KeyError, "unknown tool: #{name}" if tool.nil?

      [tool.handler.call(registry, args || {}).to_s, false]
    rescue SessionRegistry::UnknownSession,
           SessionRegistry::DuplicateSession,
           ArgumentError,
           MudManagerMcp::Session::Error => e
      ["error: #{e.message}", true]
    end
  end
end
