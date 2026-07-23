"""Port of ``mud_manager/lib/mud_manager/primitives.rb``.

Stateless generic primitives over the CircleMUD player-facing command surface.
Each function validates its enum-typed arguments and returns a :class:`Command`
describing the line to send to the MUD. Runtime preconditions (position, skill
availability, flags, room flags, equipment requirements, etc.) are
intentionally NOT checked here — they require live game state and belong to
the tool layer (``boukensha/tools/mud.py``) that wraps these primitives as
tool calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Command:
    primitive: str
    verb: str
    raw: str
    args: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.raw


DIRECTIONS = ["north", "east", "south", "west", "up", "down"]
POSITIONS = ["stand", "sit", "rest", "sleep", "wake"]
ATTACK_STYLES = ["hit", "murder", "kill"]
STRIKE_SKILLS = ["backstab", "bash", "kick", "rescue", "assist"]
LOCAL_SAY = ["say", "emote", "reply"]
TARGETED_SAY = ["tell", "whisper", "ask"]
CHANNELS = ["shout", "gossip", "auction", "grats", "holler"]
REPORT_KINDS = ["bug", "typo", "idea"]
DROP_MODES = ["drop", "donate", "junk"]
EQUIP_OPS = ["wear", "wield", "grab", "hold", "remove"]
CONSUME_MODES = ["eat", "taste", "drink", "sip"]
LIQUID_MODES = ["pour", "fill"]
DOOR_VERBS = ["open", "close", "lock", "unlock", "pick"]
LOOK_MODES = ["look", "read"]
LOOK_PREPS = ["in", "at", "north", "east", "south", "west", "up", "down"]
INFO_SELF = [
    "score", "inventory", "equipment", "gold", "exits", "time", "weather",
    "levels", "wimpy", "toggle", "where",
]
INFO_WORLD = [
    "who", "users", "help", "credits", "news", "info", "motd", "policies",
    "version", "wizlist", "immlist", "clear", "whoami",
]
LIST_KINDS = ["commands", "socials"]
COLOR_LEVELS = ["off", "sparse", "normal", "complete"]
PREF_FLAGS = [
    "autoexit", "brief", "compact", "noauction", "nogossip", "nograts",
    "norepeat", "noshout", "nosummon", "notell", "quest",
]
STEALTH_MODES = ["hide", "sneak", "visible"]
SPELL_ITEM = ["use", "quaff", "recite"]
GROUP_OPS = ["group", "ungroup"]
SHOP_OPS = ["buy", "sell", "list", "value", "offer"]
BANK_OPS = ["balance", "deposit", "withdraw"]
MAIL_OPS = ["mail", "receive", "check"]


def _check_enum(value: str, allowed: list[str], name: str) -> str:
    v = str(value).lower()
    if v not in allowed:
        raise ValueError(f"invalid {name}: {value!r} (expected one of {', '.join(allowed)})")
    return v


def _require_str(value: Any, name: str) -> None:
    if value is None or not str(value).strip():
        raise ValueError(f"{name} is required")


def _cmd(primitive: str, verb: str, raw: str, **args: Any) -> Command:
    return Command(primitive=primitive, verb=verb, raw=raw, args=args)


# ---------- Movement & posture ----------

def move(direction: str) -> Command:
    verb = _check_enum(direction, DIRECTIONS, "direction")
    return _cmd("move", verb, verb)


def enter(keyword: str | None = None) -> Command:
    raw = f"enter {keyword}" if keyword else "enter"
    return _cmd("enter", "enter", raw, target=keyword)


def leave() -> Command:
    return _cmd("leave", "leave", "leave")


def set_position(pos: str) -> Command:
    verb = _check_enum(pos, POSITIONS, "pos")
    return _cmd("set_position", verb, verb)


def follow(leader: str | None = None) -> Command:
    raw = f"follow {leader}" if leader else "follow"
    return _cmd("follow", "follow", raw, leader=leader)


def flee() -> Command:
    return _cmd("flee", "flee", "flee")


def track(victim: str) -> Command:
    _require_str(victim, "victim")
    return _cmd("track", "track", f"track {victim}", victim=victim)


# ---------- Combat ----------

def attack(style: str, target: str) -> Command:
    verb = _check_enum(style, ATTACK_STYLES, "style")
    _require_str(target, "target")
    return _cmd("attack", verb, f"{verb} {target}", target=target)


def skill_strike(skill: str, target: str) -> Command:
    verb = _check_enum(skill, STRIKE_SKILLS, "skill")
    _require_str(target, "target")
    return _cmd("skill_strike", verb, f"{verb} {target}", target=target)


def order(who: str, command: str) -> Command:
    _require_str(who, "who")
    _require_str(command, "command")
    return _cmd("order", "order", f"order {who} {command}", who=who, command=command)


def insult(target: str) -> Command:
    _require_str(target, "target")
    return _cmd("insult", "insult", f"insult {target}", target=target)


# ---------- Communication ----------

def say_local(mode: str, text: str) -> Command:
    verb = _check_enum(mode, LOCAL_SAY, "mode")
    _require_str(text, "text")
    return _cmd("say_local", verb, f"{verb} {text}", text=text)


def say_targeted(mode: str, target: str, text: str) -> Command:
    verb = _check_enum(mode, TARGETED_SAY, "mode")
    _require_str(target, "target")
    _require_str(text, "text")
    return _cmd("say_targeted", verb, f"{verb} {target} {text}", target=target, text=text)


def say_channel(channel: str, text: str) -> Command:
    verb = _check_enum(channel, CHANNELS, "channel")
    _require_str(text, "text")
    return _cmd("say_channel", verb, f"{verb} {text}", text=text)


def say_group(text: str) -> Command:
    _require_str(text, "text")
    return _cmd("say_group", "gsay", f"gsay {text}", text=text)


def say_quest(text: str) -> Command:
    _require_str(text, "text")
    return _cmd("say_quest", "qsay", f"qsay {text}", text=text)


def report_player(kind: str, text: str) -> Command:
    verb = _check_enum(kind, REPORT_KINDS, "kind")
    _require_str(text, "text")
    return _cmd("report_player", verb, f"{verb} {text}", text=text)


def write_note(paper: str, pen: str | None = None) -> Command:
    _require_str(paper, "paper")
    raw = f"write {paper} {pen}" if pen else f"write {paper}"
    return _cmd("write_note", "write", raw, paper=paper, pen=pen)


# ---------- Inventory & objects ----------

def get(obj: str, *, container: str | None = None, count: int | None = None) -> Command:
    _require_str(obj, "obj")
    parts = ["get"]
    if count:
        parts.append(str(count))
    parts.append(obj)
    if container:
        parts.append(container)
    return _cmd("get", "get", " ".join(parts), obj=obj, container=container, count=count)


def drop(mode: str, obj: str, *, count: int | None = None) -> Command:
    verb = _check_enum(mode, DROP_MODES, "mode")
    _require_str(obj, "obj")
    parts = [verb]
    if count:
        parts.append(str(count))
    parts.append(obj)
    return _cmd("drop", verb, " ".join(parts), obj=obj, count=count)


def put(obj: str, container: str, *, count: int | None = None) -> Command:
    _require_str(obj, "obj")
    _require_str(container, "container")
    parts = ["put"]
    if count:
        parts.append(str(count))
    parts.extend([obj, container])
    return _cmd("put", "put", " ".join(parts), obj=obj, container=container, count=count)


def give(obj: str, target: str, *, count: int | None = None) -> Command:
    _require_str(obj, "obj")
    _require_str(target, "target")
    parts = ["give"]
    if count:
        parts.append(str(count))
    parts.extend([obj, target])
    return _cmd("give", "give", " ".join(parts), obj=obj, target=target, count=count)


def equip(slot_op: str, obj: str, *, body_loc: str | None = None) -> Command:
    verb = _check_enum(slot_op, EQUIP_OPS, "slot_op")
    _require_str(obj, "obj")
    raw = f"{verb} {obj} {body_loc}" if body_loc else f"{verb} {obj}"
    return _cmd("equip", verb, raw, obj=obj, body_loc=body_loc)


def consume(mode: str, obj: str) -> Command:
    verb = _check_enum(mode, CONSUME_MODES, "mode")
    _require_str(obj, "obj")
    return _cmd("consume", verb, f"{verb} {obj}", obj=obj)


def transfer_liquid(mode: str, from_: str, to: str) -> Command:
    verb = _check_enum(mode, LIQUID_MODES, "mode")
    _require_str(from_, "from")
    _require_str(to, "to")
    # pour <from> <to|"out">  /  fill <to> <from>
    raw = f"pour {from_} {to}" if verb == "pour" else f"fill {to} {from_}"
    return _cmd("transfer_liquid", verb, raw, **{"from": from_, "to": to})


def split_gold(amount: int) -> Command:
    if not isinstance(amount, int) or amount <= 0:
        raise ValueError("amount must be a positive integer")
    return _cmd("split_gold", "split", f"split {amount}", amount=amount)


# ---------- Doors ----------

def door(verb: str, target: str, *, direction: str | None = None) -> Command:
    if direction is not None and not str(direction).strip():
        direction = None
    v = _check_enum(verb, DOOR_VERBS, "verb")
    _require_str(target, "target")
    if direction:
        _check_enum(direction, DIRECTIONS, "direction")
    raw = f"{v} {target} {direction}" if direction else f"{v} {target}"
    return _cmd("door", v, raw, target=target, direction=direction)


# ---------- Perception & info ----------

def look(*, mode: str = "look", target: str | None = None, preposition: str | None = None) -> Command:
    if target is not None and not str(target).strip():
        target = None
    if preposition is not None and not str(preposition).strip():
        preposition = None
    verb = _check_enum(mode, LOOK_MODES, "mode")
    if preposition:
        _check_enum(preposition, LOOK_PREPS, "preposition")
    parts = [verb]
    if preposition:
        parts.append(preposition)
    if target:
        parts.append(target)
    return _cmd("look", verb, " ".join(parts), target=target, preposition=preposition)


def examine(target: str) -> Command:
    _require_str(target, "target")
    return _cmd("examine", "examine", f"examine {target}", target=target)


def info_self(kind: str) -> Command:
    verb = _check_enum(kind, INFO_SELF, "kind")
    return _cmd("info_self", verb, verb)


def info_world(kind: str, *, filter: str | None = None) -> Command:  # noqa: A002 - matches Ruby name
    verb = _check_enum(kind, INFO_WORLD, "kind")
    raw = f"{verb} {filter}" if filter else verb
    return _cmd("info_world", verb, raw, filter=filter)


def consider(target: str) -> Command:
    _require_str(target, "target")
    return _cmd("consider", "consider", f"consider {target}", target=target)


def diagnose(target: str | None = None) -> Command:
    raw = f"diagnose {target}" if target else "diagnose"
    return _cmd("diagnose", "diagnose", raw, target=target)


def list_commands(kind: str, *, player: str | None = None) -> Command:
    verb = _check_enum(kind, LIST_KINDS, "kind")
    raw = f"{verb} {player}" if player else verb
    return _cmd("list_commands", verb, raw, player=player)


# ---------- Character / preferences / lifecycle ----------

def social(name: str, *, target: str | None = None) -> Command:
    _require_str(name, "name")
    raw = f"{name} {target}" if target else name
    return _cmd("social", name, raw, target=target)


def set_title(text: str) -> Command:
    _require_str(text, "text")
    if "(" in text or ")" in text:
        raise ValueError("title may not contain parentheses")
    return _cmd("set_title", "title", f"title {text}", text=text)


def set_display(tokens: str) -> Command:
    _require_str(tokens, "tokens")
    return _cmd("set_display", "display", f"display {tokens}", tokens=tokens)


def set_color(level: str) -> Command:
    verb = _check_enum(level, COLOR_LEVELS, "level")
    return _cmd("set_color", "color", f"color {verb}", level=verb)


def set_wimpy(hp: int) -> Command:
    if not isinstance(hp, int) or hp < 0:
        raise ValueError("hp must be a non-negative integer")
    return _cmd("set_wimpy", "wimpy", f"wimpy {hp}", hp=hp)


def toggle_pref(flag: str) -> Command:
    verb = _check_enum(flag, PREF_FLAGS, "flag")
    return _cmd("toggle_pref", verb, verb, flag=verb)


def stealth(mode: str) -> Command:
    verb = _check_enum(mode, STEALTH_MODES, "mode")
    return _cmd("stealth", verb, verb)


def steal(obj: str, victim: str) -> Command:
    _require_str(obj, "obj")
    _require_str(victim, "victim")
    return _cmd("steal", "steal", f"steal {obj} {victim}", obj=obj, victim=victim)


def practice(skill: str | None = None) -> Command:
    raw = f"practice {skill}" if skill else "practice"
    return _cmd("practice", "practice", raw, skill=skill)


def define_alias(name: str, replacement: str) -> Command:
    _require_str(name, "name")
    if name == "alias":
        raise ValueError("cannot alias 'alias'")
    _require_str(replacement, "replacement")
    return _cmd(
        "define_alias", "alias", f"alias {name} {replacement}",
        name=name, replacement=replacement,
    )


def save_char() -> Command:
    return _cmd("save_char", "save", "save")


def quit() -> Command:
    # CircleMUD requires the literal four-letter "quit" for mortals.
    return _cmd("quit", "quit", "quit")


# ---------- Magic ----------

def cast(spell: str, *, target: str | None = None) -> Command:
    _require_str(spell, "spell")
    raw = f"cast '{spell}' {target}" if target else f"cast '{spell}'"
    return _cmd("cast", "cast", raw, spell=spell, target=target)


def use_magic_item(mode: str, item: str, *, target_args: str | None = None) -> Command:
    verb = _check_enum(mode, SPELL_ITEM, "mode")
    _require_str(item, "item")
    raw = f"{verb} {item} {target_args}" if target_args else f"{verb} {item}"
    return _cmd("use_magic_item", verb, raw, item=item, target_args=target_args)


# ---------- Group ----------

def group_manage(op: str, *, target: str | None = None) -> Command:
    verb = _check_enum(op, GROUP_OPS, "op")
    raw = f"{verb} {target}" if target else verb
    return _cmd("group_manage", verb, raw, target=target)


def report_hp() -> Command:
    return _cmd("report_hp", "report", "report")


# ---------- Room-procedural (SPEC_PROC-mediated) ----------

def shop(op: str, *, args: str | None = None) -> Command:
    verb = _check_enum(op, SHOP_OPS, "op")
    raw = f"{verb} {args}" if args else verb
    return _cmd("shop", verb, raw, args=args)


def bank(op: str, *, amount: int | None = None) -> Command:
    verb = _check_enum(op, BANK_OPS, "op")
    raw = f"{verb} {amount}" if amount else verb
    return _cmd("bank", verb, raw, amount=amount)


def mail(op: str, *, recipient: str | None = None) -> Command:
    verb = _check_enum(op, MAIL_OPS, "op")
    raw = f"{verb} {recipient}" if recipient else verb
    return _cmd("mail", verb, raw, recipient=recipient)


def rent() -> Command:
    return _cmd("rent", "rent", "rent")


def house_admin(player: str | None = None) -> Command:
    raw = f"house {player}" if player else "house"
    return _cmd("house_admin", "house", raw, player=player)
