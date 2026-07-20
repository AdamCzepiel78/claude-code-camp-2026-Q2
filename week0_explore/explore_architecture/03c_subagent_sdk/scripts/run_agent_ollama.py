#!/usr/bin/env python3
"""
Interactive prompt shell for playing this tbaMUD instance through a local
Ollama model (default `gpt-oss:20b`, override with --model), instead of the
Claude Agent SDK.

Why this looks different from run_agent.py: the Claude Agent SDK version
delegates to per-character subagents (`AgentDefinition`) via the `Agent`
tool, driven by Claude's native tool-calling. Not every Ollama model has a
"tools" capability -- check with `ollama show <model>`; e.g. `gemma3:12b`
has none, `gpt-oss:20b` does -- and even one that does speaks a different
wire format than Claude's tool-use blocks. This script sidesteps that
entirely by never touching Ollama's native tool-calling API at all: every
reply is a JSON action object (see the protocol description in
SYSTEM_PROMPT_TEMPLATE below), nudged along by Ollama's loose `format="json"`
mode, which behaves the same regardless of the underlying model's own tool
support. Free-text prompting with no JSON nudge at all was tried first and
failed: asked to "look", gemma3:12b just narrated an invented room instead
of actually calling mud_client.py. `format="json"` plus the protocol
description fixed that reliably for both gemma3:12b and gpt-oss:20b.
Ollama's *strict* schema mode (`format=<json-schema>`) was tried too and
looked more robust at first, but broke gpt-oss:20b specifically: under
schema-constrained decoding it would finish its internal "thinking" channel
and then just stop with a completely empty reply (`done_reason: "stop"`,
zero content) instead of emitting the answer -- reproduced consistently in
testing, independent of the `think` on/off setting. `format="json"` doesn't
trigger that bug and both models still produce valid, well-formed replies
under it. Every MUD action funnels through the same `scripts/mud_client.py`
used by the Claude version -- nothing about the MUD login/session handling
changes.

- **Character routing**: chosen explicitly via `--character`, not decided by
  the model -- letting a local model guess which of two characters an
  ambiguous instruction means is an unnecessary failure mode to invite.
- **Progress logging**: local models can take anywhere from a couple of
  seconds to several minutes per action (slower models, longer
  conversations, GPU vs. CPU), and a multi-step player instruction can
  trigger many actions in one turn. Every step -- asking the model, its
  thought/action choice, and dispatching that action -- is logged with a
  timestamp and elapsed time as it happens (see `_log()` below), so a long
  turn reads as "still working" instead of looking hung.

Run it and type MUD commands / instructions at the `mud> ` prompt, one per
line. Type "exit", "quit", or press Ctrl-D to leave the shell.

Usage:
    python3 scripts/run_agent_ollama.py --character dummy
    python3 scripts/run_agent_ollama.py --character jibbus --model gemma3:12b
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import ollama

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MUD_CLIENT = PROJECT_ROOT / "scripts" / "mud_client.py"


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

MAX_TRANSCRIPT_CHARS = 4000  # keep MUD output observations bounded for a 12B context budget
MAX_ACTIONS_PER_TURN = 20  # hard cap so a runaway model can't hang the REPL forever

# Ollama defaults num_ctx to 4096 regardless of a model's real max context
# (131072 for both gemma3:12b and gpt-oss:20b per `ollama show`). Diagnosed
# in testing: by the 3rd action in a turn -- system prompt (~2000 tokens) +
# one MUD observation + one READ_PLAYER dump of a real player.md (~1550
# tokens) -- prompt_eval_count was already 3857/4096, leaving so little room
# that generation hit done_reason="length" and got cut off before ever
# emitting closing JSON, which looked like (and was reported as) "invalid
# JSON replies". 32768 confirmed to still load 100% on GPU for gpt-oss:20b
# on this machine; raise it further if VRAM allows and sessions still run
# into it on long play sessions.
NUM_CTX = 32768

# Same per-character facts the Claude Agent SDK version hardcodes in
# run_agent.py -- mud_client.py's own --user/--password defaults only match
# "dummy", so every invocation below passes credentials explicitly.
CHARACTERS = {
    "dummy": {
        "password": "helloworld",
        "exits_note": (
            "`dummy` has `autoexits` toggled on (confirmed), so every `look` "
            "and every move already ends with an `Exits: n e s w` style line "
            "-- don't spend a separate action calling `exits` just to see "
            "what's around; read the line you already have."
        ),
        "brief_note": (
            "`dummy` plays with brief mode off on purpose (confirmed -- room "
            "text often hides real gameplay hints, see `help brief` in-game), "
            "so the full description shows every time you enter. Once you "
            "have a room's description this session, move on instead of "
            "calling `look` again out of habit."
        ),
        "extra_notes": "",
    },
    "jibbus": {
        "password": "password",
        "exits_note": (
            "Not yet confirmed whether `autoexits` is on for this account -- "
            "it's a per-character toggle, it does NOT carry over from "
            "`dummy`. Check on an early `look`/move; if an `Exits:` line "
            "isn't appended automatically, run `exits` once, then record the "
            "result in `data/jibbus/player.md` so you don't re-check it "
            "every turn."
        ),
        "brief_note": (
            "Not yet confirmed whether brief mode is on or off for this "
            "account -- it's a per-character toggle, it does NOT carry over "
            "from `dummy`. If room descriptions look truncated, consider "
            "`brief` off (see `help brief`) so full text shows each time; "
            "record whichever mode this account turns out to be in inside "
            "`data/jibbus/player.md`."
        ),
        "extra_notes": (
            "\nNew character -- no play history yet. If data/jibbus/player.md "
            "still has 'unknown' placeholders, run score, inventory, and "
            "equipment on first login and fill in every section instead of "
            "leaving it unknown. Do not assume anything about this "
            "character's level, gear, or toggle settings from dummy's "
            "history; they are entirely separate characters that happen to "
            "share the same MUD world.\n"
        ),
    },
}

SYSTEM_PROMPT_TEMPLATE = """\
You play the character `{character}` on the tbaMUD instance at
localhost:4000. You are a game-playing agent, NOT a narrator -- you have
never seen this world and must never invent room descriptions, NPCs, exits,
combat outcomes, or numbers yourself. Everything you know about the current
game state comes only from real OBSERVATION messages this script gives you
after each action.

Every reply you produce must be a single JSON object with a "thought" field
first (one short sentence: what do you need right now, and which action
gets it), then an "action" field, then whichever of "command" / "content" /
"message" that action uses:

- {{"action": "MUD", "command": "<one command, or several separated by ' ; '>"}}
  Runs real command(s) against the live MUD server and returns their actual
  output as your next observation. This is your ONLY way to see or affect
  the game -- if the player's request needs current game state and you
  haven't run a command for it yet this turn, this is what your reply must
  be, not a SAY.
- {{"action": "MUD_QUIT", "command": "<optional final command(s), or empty"}}
  Same as MUD, but also fully logs the character out afterward.
- {{"action": "READ_PLAYER"}} / {{"action": "READ_WORLD"}}
  Returns the current content of data/{character}/player.md or
  data/world.md as your next observation. This is the ONLY way you see
  either file -- their content is NOT preloaded into this conversation.
- {{"action": "WRITE_PLAYER", "content": "<entire new file content>"}} /
  {{"action": "WRITE_WORLD", "content": "<entire new file content>"}}
  Replaces the WHOLE file -- you must READ it first in this same session so
  you know its current content, then copy forward everything still true and
  only change what changed, in the same terse bullet style already used.
  Never WRITE a file you haven't READ this session.
- {{"action": "SAY", "message": "<what you tell the player>"}}
  Ends your turn. Use it once you've actually run whatever MUD/READ actions
  the request needed and can answer from their real output -- not before.

Exactly one action per reply. No text outside the JSON object.

**If the player's message is itself a MUD command or phrase** (e.g. "look",
"north", "score", "inventory", "kill fido", "say hello"), your first action
this turn must be {{"action": "MUD", "command": "<that exact text>"}} --
never substitute a remembered description or a file read for actually
running it. A SAY's "message" must never be empty -- if you have nothing to
add yet, take another action instead of saying nothing.

**At the start of a session** (the first player message after this system
prompt, or whenever you're unsure where the character currently stands),
READ_PLAYER before doing anything else that depends on level/HP/position --
don't guess or ask the player something the file already answers.

## Running MUD commands (action "MUD" / "MUD_QUIT")

Each command in "command" is sent to the game in order via `mud_client.py`,
which handles the connection, telnet negotiation, and login sequence
deterministically -- you never talk to the socket yourself. Examples:
"look", "north ; north ; look", "score ; inventory".

If an observation says "Could not connect to localhost:4000 -- ...", the MUD
is currently down -- tell the player via SAY and don't retry more than once
or twice.

## Session model -- read this before choosing MUD vs MUD_QUIT

The character persists in the game world across separate script invocations,
the same way a real MUD stays running when your telnet client loses its
connection. Action "MUD" closes the socket afterward WITHOUT sending `quit`,
leaving the character link-dead so the next action resumes exactly where you
left off (same room, same state). Because of this:
- You can issue many "MUD" actions in a row to carry out a multi-step goal
  (e.g. navigate room by room). There's no need to cram everything into one
  "command" string.
- Only use "MUD_QUIT" when the player actually wants to end the play
  session -- it fully logs the character out to the numbered character menu,
  which is extra round-trips to undo next time. Never use it just to "clean
  up" after a normal action.

## Persistent memory -- data/{character}/player.md and data/world.md

The character's link-dead persistence (above) covers state *within* the game
server, but nothing about a session's commands is remembered on its own --
without a written record, every new session would re-derive the map and
character state from scratch. Two files carry that knowledge forward
instead (READ_PLAYER / READ_WORLD to see either one):

- **data/{character}/player.md** -- this character's own sheet: level,
  vitals, exp/gold, known kill-worthy mobs and their `consider` results,
  inventory/equipment, goals in progress. Never touch another character's
  player.md.
- **data/world.md** -- the map, shared by every character played in this
  project: every room discovered so far (name, exits, NPCs, notes), known
  routes between landmarks, and an "unexplored leads" list. Add to it for
  everyone's benefit; never put {character}-specific state (HP, gold,
  inventory, position) here -- that only belongs in player.md.

**Update both files as you play**, not just at the end:
- player.md -- whenever HP/mana/movement, exp/gold, level, alignment,
  inventory/equipment, or position changes meaningfully (a kill, a level-up,
  a shop transaction, a death, ending the session in a new room).
- world.md -- the moment you see a room that isn't already recorded: its
  exact name, exits, NPCs, and any notable feature. Add newly learned routes
  under a "Route:" heading like the existing ones. Move items out of
  "Unexplored leads" once resolved, and add new ones as they come up.

Stale or wrong entries are worse than missing ones: if something you find
contradicts what's recorded (a room redescribed, a mob that fled), correct
it in place rather than leaving both versions.

**Mandatory end-of-turn checkpoint.** Before your SAY in any turn that ran
MUD commands, ask yourself: has anything happened since the last file write
that player.md or world.md doesn't reflect yet (a kill, a level-up, gold/exp
change, a new room, a new "too dangerous" mob)? If yes, issue a
WRITE_PLAYER and/or WRITE_WORLD action before your SAY -- don't defer it to
"next session."

## Playing effectively

- **Exits:** {exits_note}
- **Room description verbosity:** {brief_note}
- **`consider <target>` before you fight anything unfamiliar.** It's a free,
  rough level comparison (no HP/damage info) that costs nothing and can save
  you from a fight you'd need to `flee`. `flee` only works if there's an open
  exit, so don't fight with your back against a dead end.
- **Recover between fights** with `rest` (or `sleep`) then `stand` -- faster
  than walking damage off, and `score` tells you how banged up you are if
  you're not sure.
- **Reach for the specific check you need**: `score` (level/exp/alignment/
  quest points), `inventory`/`i` (what you're carrying), `equipment`/`eq`
  (what you're wearing) are three different answers -- don't run all three
  when only one answers the actual question.
- **Shops need `list` first** to see what's on offer before `buy`/`sell`/
  `value`. `gold` is cash on hand; `balance`/`deposit`/`withdraw` is the
  bank.
{extra_notes}
For anything not covered here -- the full command set, class-specific
skills, quest mechanics -- see references/commands.md, or issue
`help <command>` as a MUD command in-game, which is authoritative if the
server config ever changes.
"""


def read_data_file(character: str, name: str) -> str:
    if name == "player.md":
        path = PROJECT_ROOT / "data" / character / "player.md"
    else:
        path = PROJECT_ROOT / "data" / "world.md"
    try:
        return path.read_text()
    except FileNotFoundError:
        return f"(file does not exist yet: {path.relative_to(PROJECT_ROOT)})"


# A 12B model can go off the rails mid-session (observed in testing: it
# started emitting empty/near-empty WRITE_PLAYER content over and over,
# which would silently wipe a character sheet with real play history). A
# WRITE that would shrink an existing non-trivial file by more than this is
# refused outright rather than trusting the model's judgment -- there's no
# legitimate edit this small script needs to make that loses most of a file
# in one shot.
MIN_WRITE_KEEP_RATIO = 0.3


def write_data_file(character: str, name: str, content: str) -> str:
    if name == "player.md":
        path = PROJECT_ROOT / "data" / character / "player.md"
    else:
        path = PROJECT_ROOT / "data" / "world.md"
    content = content.rstrip()
    existing = path.read_text() if path.exists() else ""
    if len(existing) > 200 and len(content) < len(existing) * MIN_WRITE_KEEP_RATIO:
        return (
            f"REFUSED: new content ({len(content)} chars) would shrink "
            f"{path.relative_to(PROJECT_ROOT)} from {len(existing)} chars by "
            "more than 70% -- this looks like an accidental wipe, not a real "
            "update, so it was not written. If the player actually wants "
            "this file drastically cut down, they need to say so explicitly."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content + "\n")
    return f"Wrote {path.relative_to(PROJECT_ROOT)} ({len(content)} chars)."


def build_system_prompt(character: str) -> str:
    cfg = CHARACTERS[character]
    return SYSTEM_PROMPT_TEMPLATE.format(
        character=character,
        exits_note=cfg["exits_note"],
        brief_note=cfg["brief_note"],
        extra_notes=cfg["extra_notes"],
    )


def run_mud_client(character: str, commands: list[str], quit_session: bool) -> str:
    cfg = CHARACTERS[character]
    argv = [
        sys.executable,
        str(MUD_CLIENT),
        "--user", character,
        "--password", cfg["password"],
    ]
    if quit_session:
        argv.append("--quit")
    argv.extend(commands)
    try:
        result = subprocess.run(
            argv, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        return "MUD ERROR: mud_client.py timed out after 60s."
    output = result.stdout
    if result.returncode != 0:
        output += "\n" + result.stderr
    if len(output) > MAX_TRANSCRIPT_CHARS:
        output = output[:MAX_TRANSCRIPT_CHARS] + "\n... (truncated)"
    return output


VALID_ACTIONS = {
    "MUD", "MUD_QUIT", "READ_PLAYER", "READ_WORLD",
    "WRITE_PLAYER", "WRITE_WORLD", "SAY",
}


def parse_action(reply: str) -> dict | None:
    """`format="json"` only guarantees well-formed JSON, not that it matches
    our action protocol, and in testing replies have come back wrong in a
    few different ways: empty or cut off mid-object (e.g. a bare
    '{"thought": "I' with no closing, or gpt-oss:20b's empty-content bug
    under the stricter schema mode this used to use -- see the module
    docstring), or -- observed after switching to format="json" -- a
    correctly-shaped-looking object whose "action" value is itself a
    stringified dict, e.g. {"action": "{'action': 'MUD', ...}"}. Returns
    None for any of those cases so the caller can ask the model to retry
    instead of treating the fragment as a real SAY or a real action.
    """
    try:
        parsed = json.loads(reply)
        # "action" can come back as a nested dict/list instead of a string
        # (observed in testing) -- isinstance guards the `in` check below,
        # since `some_dict in a_set` raises TypeError (unhashable type)
        # rather than just being False.
        if isinstance(parsed, dict) and isinstance(parsed.get("action"), str) \
                and parsed["action"] in VALID_ACTIONS:
            return parsed
    except json.JSONDecodeError:
        pass
    return None


def _split_commands(raw: str) -> list[str]:
    return [c.strip() for c in (raw or "").split(";") if c.strip()]


def execute_action(character: str, parsed: dict) -> tuple[str | None, str]:
    """Returns (observation_for_model, display_text). observation is None for SAY."""
    action = parsed.get("action", "SAY")

    if action == "MUD":
        commands = _split_commands(parsed.get("command", ""))
        transcript = run_mud_client(character, commands, quit_session=False)
        return transcript, f"> {' ; '.join(commands) or '(no commands)'}\n{transcript}"

    if action == "MUD_QUIT":
        commands = _split_commands(parsed.get("command", ""))
        transcript = run_mud_client(character, commands, quit_session=True)
        label = " ; ".join(commands + ["quit"])
        return transcript, f"> {label}\n{transcript}"

    if action == "READ_PLAYER":
        content = read_data_file(character, "player.md")
        return content, "  [read player.md]"

    if action == "READ_WORLD":
        content = read_data_file(character, "world.md")
        return content, "  [read world.md]"

    if action == "WRITE_PLAYER":
        result = write_data_file(character, "player.md", parsed.get("content", ""))
        return result, f"  [{result}]"

    if action == "WRITE_WORLD":
        result = write_data_file(character, "world.md", parsed.get("content", ""))
        return result, f"  [{result}]"

    if action == "SAY":
        message = (parsed.get("message") or "").strip()
        if not message:
            return (
                "Your SAY message was empty, which isn't a valid reply. If "
                "you haven't checked the game state yet, issue a MUD action "
                "for it now; otherwise provide an actual message.",
                "  [empty SAY -- retrying]",
            )
        return None, message

    return f"Unknown action {action!r}.", f"  [unknown action {action!r}]"


MAX_MALFORMED_RETRIES = 3  # consecutive unparseable replies before giving up on the turn


def run_turn(client: "ollama.Client", model: str, character: str, messages: list) -> None:
    # Loop-detection: a local model can get stuck repeating the exact same
    # action (observed in testing) instead of noticing it isn't progressing.
    # Bail out early rather than burning all MAX_ACTIONS_PER_TURN attempts.
    recent_fingerprints: list[str] = []
    malformed_count = 0

    for i in range(MAX_ACTIONS_PER_TURN):
        _log(f"action {i + 1}/{MAX_ACTIONS_PER_TURN}: asking {model} for the next step...")
        # A local model can hand back shapes we didn't anticipate (e.g. an
        # "action" value that's itself a nested dict, seen in testing, which
        # crashed an earlier version of this check with an uncaught
        # TypeError). Anything unexpected in here is treated the same way as
        # a malformed reply -- logged, retried up to MAX_MALFORMED_RETRIES --
        # rather than ever taking down the whole interactive session.
        try:
            t0 = time.monotonic()
            response = client.chat(
                model=model, messages=messages, format="json",
                options={"num_ctx": NUM_CTX},
            )
            model_elapsed = time.monotonic() - t0
            reply = response["message"]["content"]
            messages.append({"role": "assistant", "content": reply})

            parsed = parse_action(reply)
            if parsed is None:
                malformed_count += 1
                _log(f"  ({model_elapsed:.1f}s) reply wasn't valid JSON -- asking for a retry "
                     f"({malformed_count}/{MAX_MALFORMED_RETRIES})")
                if malformed_count >= MAX_MALFORMED_RETRIES:
                    print("  [gave up after repeated malformed replies -- try rephrasing]")
                    return
                messages.append({
                    "role": "user",
                    "content": "[OBSERVATION]\nThat reply was not a complete, valid JSON "
                                "object matching the schema. Send a fresh, complete reply.",
                })
                continue
            malformed_count = 0

            action_name = parsed.get("action", "SAY")
            thought = parsed.get("thought", "")
            detail = f" {parsed['command']!r}" if action_name in ("MUD", "MUD_QUIT") and parsed.get("command") else ""
            _log(f"  ({model_elapsed:.1f}s) thought: {thought!r}")
            _log(f"  -> dispatching {action_name}{detail}")

            t0 = time.monotonic()
            observation, display = execute_action(character, parsed)
            action_elapsed = time.monotonic() - t0

            if observation is None:  # action "SAY" -- turn is over
                _log(f"  <- SAY, turn done ({action_elapsed:.1f}s)")
                print(display)
                return

            # Exclude "thought" -- its wording can vary turn to turn even when
            # the actual action is stuck repeating, which is what we want to catch.
            fingerprint = json.dumps({k: v for k, v in parsed.items() if k != "thought"}, sort_keys=True)
            recent_fingerprints.append(fingerprint)
            if recent_fingerprints[-3:] == [fingerprint] * 3:
                print("  [repeated the same action 3 times in a row -- stopping this turn]")
                return

            _log(f"  <- done in {action_elapsed:.1f}s")
            print(display)
            messages.append({"role": "user", "content": f"[OBSERVATION]\n{observation}"})
        except Exception as exc:
            malformed_count += 1
            _log(f"  unexpected error processing this step: {exc!r} "
                 f"({malformed_count}/{MAX_MALFORMED_RETRIES})")
            if malformed_count >= MAX_MALFORMED_RETRIES:
                print("  [gave up after repeated errors -- try rephrasing]")
                return
            messages.append({
                "role": "user",
                "content": "[OBSERVATION]\nThat last step hit an internal error and was "
                            "skipped. Send a fresh, complete reply.",
            })

    print(f"  [stopped after {MAX_ACTIONS_PER_TURN} actions without a SAY -- "
          "ask the player something narrower next time]")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--character", choices=sorted(CHARACTERS), required=True,
                         help="which MUD character to play as")
    parser.add_argument("--model", default="gpt-oss:20b", help="Ollama model to use")
    parser.add_argument("--host", default=None, help="Ollama server URL (default: OLLAMA_HOST env or localhost:11434)")
    args = parser.parse_args()

    client = ollama.Client(host=args.host)
    system_prompt = build_system_prompt(args.character)
    messages = [{"role": "system", "content": system_prompt}]

    print(f"MUD agent shell (Ollama/{args.model}) -- playing as `{args.character}`.")
    print('Type in-game commands or instructions. Type "exit", "quit", or Ctrl-D to leave.\n')

    while True:
        try:
            line = input("mud> ")
        except EOFError:
            print()
            break

        line = line.strip()
        if not line:
            continue
        if line.lower() in {"exit", "quit"}:
            break

        messages.append({"role": "user", "content": line})
        try:
            run_turn(client, args.model, args.character, messages)
        except Exception as exc:
            # Last-resort net: run_turn already retries internally on bad
            # replies, but nothing should be able to kill the whole shell
            # (and the player's ability to keep typing) over one bad turn.
            _log(f"  turn crashed unexpectedly: {exc!r} -- shell is still alive, try again")

    print("Goodbye.")


if __name__ == "__main__":
    main()
