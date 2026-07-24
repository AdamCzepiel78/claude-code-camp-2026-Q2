"""Port of ``lib/boukensha/tools/mud.rb``.

``register`` registers MUD-gameplay tools against a registry.

A single ``mud_manager.Session`` is created when the tools are registered and
shared by every tool via closure — the agent logs in once and reuses the
connection for all subsequent tool calls.

``mud_manager`` is vendored one level up at ``python/mud_manager/`` (a sibling
of every step directory, not nested inside this step) — mirroring the Ruby
original, which is its own gem (``week1_baseline/mud_manager_mcp``) pulled in as a
dependency rather than duplicated per step. This module adds that directory's
parent onto ``sys.path`` before importing it.

Tools registered (grouped by concern):

  Connection
    mud_connect       — open socket and log in
    mud_disconnect    — close socket gracefully
    mud_status        — report whether the session is open

  Perception
    look              — look at the room or a specific target
    examine           — examine something in detail
    check             — query self-info (score, inventory, equipment, exits, gold…)

  Movement
    move              — go a compass direction or up/down
    flee              — flee from combat
    set_position      — change body position (stand/sit/rest/sleep/wake)
    track             — track a mob or player by name to find their direction

  Combat
    attack            — attack a target (kill / hit / murder)
    skill_strike      — use a combat skill (bash, kick, backstab, rescue, assist)
    consider          — assess a mob's relative strength before fighting

  Communication
    say               — say/emote/reply in the room
    tell              — tell/whisper/ask a specific player
    channel_say       — broadcast over a channel (shout, gossip, auction…)

  Inventory & equipment
    get_item          — pick up an item (optionally from a container)
    drop_item         — drop, donate, or junk an item
    put_item          — put an item into a container
    equip_item        — wear, wield, hold, grab, or remove an item
    consume_item      — eat, drink, taste, or sip something

  Magic
    cast_spell        — cast a named spell with an optional target
    use_magic_item    — quaff a potion, recite a scroll, or use a wand/staff

  Utility
    shop              — buy, sell, list, or value items at a shop
    practice          — list or practice a skill with a guildmaster
    save_character    — save the character to disk
    send_raw          — send an arbitrary command string (escape hatch)

Usage::

    boukensha.tools.mud.register(
        registry,
        host="localhost",
        port=4000,
        name="Gandalf",
        password="secret",
    )
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from boukensha.registry import Registry

# python/mud_manager/ is a sibling of every step directory (this file lives at
# <step>/boukensha/tools/mud.py, so parents[3] is the `python/` directory).
_PYTHON_DIR = Path(__file__).resolve().parents[3]
if str(_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(_PYTHON_DIR))

import mud_manager  # noqa: E402 - sys.path must be patched first
from mud_manager import primitives as p  # noqa: E402


def register(registry: Registry, *, host: str = "localhost", port: int = 4000, name: str, password: str) -> None:
    session = mud_manager.Session(host=host, port=port)

    def send_cmd(command: Any) -> str:
        """Send a primitive command and return the MUD's response text.

        Drains any stale buffered bytes (leftover login output, async ticks,
        etc.) before sending so ``read_until_prompt`` sees only fresh data
        produced by this command, then waits for CircleMUD's "> " prompt
        sentinel, which the server always appends at the end of a response.
        """
        session.drain()
        session.send_command(command)
        return session.read_until_prompt()

    def guard() -> str | None:
        """Return an error string if the session is not open so the agent can
        decide whether to call mud_connect first."""
        if not session.is_open():
            return "error: not connected — call mud_connect first"
        return None

    # ── Connection ─────────────────────────────────────────────────────

    @registry.tool(
        "mud_connect",
        description="Open the connection to the MUD server and log in with the configured "
        "character name and password. Safe to call when already connected "
        "(returns current status instead of reconnecting).",
        parameters={},
    )
    def mud_connect() -> str:
        if session.is_open():
            return f"already connected to {session.host}:{session.port}"
        try:
            session.open()
            welcome = session.login(name, password)
            return f"connected to {session.host}:{session.port}\n{welcome}"
        except mud_manager.SessionError as e:
            return f"error: {e}"

    @registry.tool(
        "mud_disconnect",
        description="Close the connection to the MUD server gracefully.",
        parameters={},
    )
    def mud_disconnect() -> str:
        if session.is_open():
            session.close()
            return "disconnected"
        return "already disconnected"

    @registry.tool(
        "mud_status",
        description="Return whether the MUD session is currently connected.",
        parameters={},
    )
    def mud_status() -> str:
        return f"connected to {session.host}:{session.port}" if session.is_open() else "disconnected"

    # ── Perception ──────────────────────────────────────────────────────

    @registry.tool(
        "look",
        description="Look at the current room or at a specific target. Call with NO arguments "
        "to describe the current room (do NOT pass target: 'room'). Pass a target to "
        "inspect a specific item, mob, or player (e.g. target: 'sword'). Use preposition "
        "'in' to look inside a container, 'at' to inspect something, or a direction "
        "(north/east/south/west/up/down) to peek into an adjacent room.",
        parameters={
            "target": {
                "type": "string",
                "description": "Item, mob, or player name to inspect. Omit entirely to "
                "describe the current room.",
            },
            "preposition": {
                "type": "string",
                "description": "Preposition: in, at, north, east, south, west, up, down (optional)",
            },
        },
    )
    def look(target: str | None = None, preposition: str | None = None) -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.look(target=target, preposition=preposition))
        except ValueError as e:
            return f"error: {e}"

    @registry.tool(
        "examine",
        description="Examine a target in detail (more verbose than look).",
        parameters={
            "target": {"type": "string", "description": "The item, mob, or player to examine"},
        },
    )
    def examine(target: str) -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.examine(target))
        except ValueError as e:
            return f"error: {e}"

    @registry.tool(
        "check",
        description="Query information about your character or surroundings. Kinds: score, "
        "inventory, equipment, gold, exits, time, weather, levels, wimpy, toggle, where.",
        parameters={
            "kind": {
                "type": "string",
                "description": "What to check: score | inventory | equipment | gold | exits | "
                "time | weather | levels | wimpy | toggle | where",
            },
        },
    )
    def check(kind: str) -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.info_self(kind))
        except ValueError as e:
            return f"error: {e}"

    # ── Movement ────────────────────────────────────────────────────────

    @registry.tool(
        "move",
        description="Move in a compass direction or up/down.",
        parameters={
            "direction": {"type": "string", "description": "Direction: north | east | south | west | up | down"},
        },
    )
    def move(direction: str) -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.move(direction))
        except ValueError as e:
            return f"error: {e}"

    @registry.tool(
        "flee",
        description="Attempt to flee from combat in a random available direction.",
        parameters={},
    )
    def flee() -> str:
        if err := guard():
            return err
        return send_cmd(p.flee())

    @registry.tool(
        "set_position",
        description="Change body position. Use 'rest' or 'sleep' between fights to recover HP "
        "and mana. Must be standing to move or fight.",
        parameters={
            "position": {"type": "string", "description": "Position: stand | sit | rest | sleep | wake"},
        },
    )
    def set_position(position: str) -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.set_position(position))
        except ValueError as e:
            return f"error: {e}"

    @registry.tool(
        "track",
        description="Attempt to track a mob or player by name, revealing which direction they "
        "are in. Requires the Track skill.",
        parameters={
            "target": {"type": "string", "description": "Name of the mob or player to track"},
        },
    )
    def track(target: str) -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.track(target))
        except ValueError as e:
            return f"error: {e}"

    # ── Combat ──────────────────────────────────────────────────────────

    @registry.tool(
        "attack",
        description="Attack a target. Style 'kill' is the standard approach; 'murder' bypasses "
        "the mercy check; 'hit' is a one-off strike.",
        parameters={
            "target": {"type": "string", "description": "Name of the mob or player to attack"},
            "style": {"type": "string", "description": "Attack style: kill | hit | murder (default: kill)"},
        },
    )
    def attack(target: str, style: str = "kill") -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.attack(style, target))
        except ValueError as e:
            return f"error: {e}"

    @registry.tool(
        "skill_strike",
        description="Use a combat skill against a target.",
        parameters={
            "skill": {"type": "string", "description": "Skill: bash | kick | backstab | rescue | assist"},
            "target": {"type": "string", "description": "Name of the mob or player"},
        },
    )
    def skill_strike(skill: str, target: str) -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.skill_strike(skill, target))
        except ValueError as e:
            return f"error: {e}"

    @registry.tool(
        "consider",
        description="Assess a mob's relative strength before engaging in combat. Returns a "
        "phrase such as 'You could kill it easily' or 'Death awaits you'. Always consider "
        "before attacking an unknown mob.",
        parameters={
            "target": {"type": "string", "description": "Name of the mob to consider"},
        },
    )
    def consider(target: str) -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.consider(target))
        except ValueError as e:
            return f"error: {e}"

    # ── Communication ───────────────────────────────────────────────────

    @registry.tool(
        "say",
        description="Speak or emote in the current room.",
        parameters={
            "text": {"type": "string", "description": "What to say or emote"},
            "mode": {"type": "string", "description": "Mode: say | emote | reply (default: say)"},
        },
    )
    def say(text: str, mode: str = "say") -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.say_local(mode, text))
        except ValueError as e:
            return f"error: {e}"

    @registry.tool(
        "tell",
        description="Send a private message to a specific player.",
        parameters={
            "target": {"type": "string", "description": "Player name to message"},
            "text": {"type": "string", "description": "The message"},
            "mode": {"type": "string", "description": "Mode: tell | whisper | ask (default: tell)"},
        },
    )
    def tell(target: str, text: str, mode: str = "tell") -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.say_targeted(mode, target, text))
        except ValueError as e:
            return f"error: {e}"

    @registry.tool(
        "channel_say",
        description="Broadcast a message over a global channel.",
        parameters={
            "channel": {"type": "string", "description": "Channel: shout | gossip | auction | grats | holler"},
            "text": {"type": "string", "description": "The message to broadcast"},
        },
    )
    def channel_say(channel: str, text: str) -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.say_channel(channel, text))
        except ValueError as e:
            return f"error: {e}"

    # ── Inventory & equipment ────────────────────────────────────────────

    @registry.tool(
        "get_item",
        description="Pick up an item from the room or from a container.",
        parameters={
            "item": {"type": "string", "description": "Name of the item to get"},
            "container": {"type": "string", "description": "Container to get it from (optional)"},
            "count": {"type": "integer", "description": "Number of items to get (optional)"},
        },
    )
    def get_item(item: str, container: str | None = None, count: int | None = None) -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.get(item, container=container, count=count))
        except ValueError as e:
            return f"error: {e}"

    @registry.tool(
        "drop_item",
        description="Drop, donate, or junk an item.",
        parameters={
            "item": {"type": "string", "description": "Name of the item"},
            "mode": {"type": "string", "description": "Mode: drop | donate | junk (default: drop)"},
            "count": {"type": "integer", "description": "Number of items (optional)"},
        },
    )
    def drop_item(item: str, mode: str = "drop", count: int | None = None) -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.drop(mode, item, count=count))
        except ValueError as e:
            return f"error: {e}"

    @registry.tool(
        "put_item",
        description="Put an item into a container.",
        parameters={
            "item": {"type": "string", "description": "Name of the item to put"},
            "container": {"type": "string", "description": "Name of the container"},
            "count": {"type": "integer", "description": "Number of items (optional)"},
        },
    )
    def put_item(item: str, container: str, count: int | None = None) -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.put(item, container, count=count))
        except ValueError as e:
            return f"error: {e}"

    @registry.tool(
        "equip_item",
        description="Wear, wield, hold, grab, or remove an item.",
        parameters={
            "item": {"type": "string", "description": "Name of the item"},
            "action": {"type": "string", "description": "Action: wear | wield | hold | grab | remove"},
            "body_loc": {"type": "string", "description": "Body location to wear on (optional, e.g. 'head', 'finger')"},
        },
    )
    def equip_item(item: str, action: str, body_loc: str | None = None) -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.equip(action, item, body_loc=body_loc))
        except ValueError as e:
            return f"error: {e}"

    @registry.tool(
        "consume_item",
        description="Eat, drink, taste, or sip a consumable item.",
        parameters={
            "item": {"type": "string", "description": "Name of the item to consume"},
            "mode": {"type": "string", "description": "Mode: eat | drink | taste | sip (default: eat)"},
        },
    )
    def consume_item(item: str, mode: str = "eat") -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.consume(mode, item))
        except ValueError as e:
            return f"error: {e}"

    # ── Magic ────────────────────────────────────────────────────────────

    @registry.tool(
        "cast_spell",
        description="Cast a spell, optionally at a target.",
        parameters={
            "spell": {"type": "string", "description": "Full spell name (e.g. 'cure light wounds', 'magic missile')"},
            "target": {"type": "string", "description": "Target mob, player, or object (optional)"},
        },
    )
    def cast_spell(spell: str, target: str | None = None) -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.cast(spell, target=target))
        except ValueError as e:
            return f"error: {e}"

    @registry.tool(
        "use_magic_item",
        description="Activate a magic item: quaff a potion, recite a scroll, or use a wand/staff.",
        parameters={
            "item": {"type": "string", "description": "Name of the item to activate"},
            "mode": {"type": "string", "description": "Mode: quaff | recite | use"},
            "target_args": {"type": "string", "description": "Optional target arguments (e.g. mob name for a wand)"},
        },
    )
    def use_magic_item(item: str, mode: str, target_args: str | None = None) -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.use_magic_item(mode, item, target_args=target_args))
        except ValueError as e:
            return f"error: {e}"

    # ── Utility ──────────────────────────────────────────────────────────

    @registry.tool(
        "shop",
        description="Interact with a shop NPC: list stock, buy, sell, or get the value of an item.",
        parameters={
            "action": {"type": "string", "description": "Action: list | buy | sell | value | offer"},
            "args": {"type": "string", "description": "Item name or number (optional)"},
        },
    )
    def shop(action: str, args: str | None = None) -> str:
        if err := guard():
            return err
        try:
            return send_cmd(p.shop(action, args=args))
        except ValueError as e:
            return f"error: {e}"

    @registry.tool(
        "practice",
        description="List your known skills at a guildmaster, or practice a specific skill.",
        parameters={
            "skill": {"type": "string", "description": "Skill name to practice (omit to list all)"},
        },
    )
    def practice(skill: str | None = None) -> str:
        if err := guard():
            return err
        return send_cmd(p.practice(skill))

    @registry.tool(
        "save_character",
        description="Save your character to disk so progress is not lost on disconnect.",
        parameters={},
    )
    def save_character() -> str:
        if err := guard():
            return err
        return send_cmd(p.save_char())

    @registry.tool(
        "send_raw",
        description="Send an arbitrary command string to the MUD and return the response. Use "
        "this as an escape hatch when no structured tool fits.",
        parameters={
            "command": {"type": "string", "description": "The raw command to send (e.g. 'who', 'help backstab')"},
        },
    )
    def send_raw(command: str) -> str:
        if err := guard():
            return err
        session.send_command(command)
        return session.read_until_quiet()

    # Auto-connect at startup so the session is ready immediately and the
    # agent doesn't need to waste a turn calling mud_connect first.
    try:
        session.open()
        session.login(name, password)
    except mud_manager.SessionError as e:
        print(f"[boukensha] MUD auto-connect failed: {e} — call mud_connect manually", file=sys.stderr)
