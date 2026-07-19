#!/usr/bin/env python3
"""
Interactive prompt shell for playing this tbaMUD instance through the
Claude Agent SDK. Two characters are known -- `dummy` and `jibbus` -- each
driven by its own subagent, defined via `AgentDefinition` rather than a
filesystem `.claude/agents/*.md` file.

Run it and type MUD commands / instructions at the `mud> ` prompt, one per
line -- each line is sent to the orchestrator, which delegates to whichever
character's subagent (`play-mud-dummy` or `play-mud-jibbus`) fits the
request, via the Agent tool, to actually drive the game. Type "exit",
"quit", or press Ctrl-D to leave the shell.

Usage:
    python3 scripts/run_agent.py
"""
import asyncio
from pathlib import Path

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TaskNotificationMessage,
    TaskProgressMessage,
    TaskStartedMessage,
    TaskUpdatedMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# One entry per known MUD character. mud_client.py's own --user/--password
# defaults only match "dummy" -- every agent below passes its credentials
# explicitly on every invocation so neither character can accidentally act
# as the other.
CHARACTERS = {
    "dummy": {
        "password": "helloworld",
        "exits_note": (
            "`dummy` has `autoexits` toggled on (confirmed), so every `look` "
            "and every move already ends with an `Exits: n e s w` style line "
            "-- don't spend a separate turn calling `exits` just to see "
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
            "\n## New character -- no play history yet\n\n"
            "`jibbus` was only just created (2026-07-19) and has no prior "
            "sessions. `data/jibbus/player.md` is a blank template with "
            "`unknown` placeholders -- on first login, run `score`, "
            "`inventory`, and `equipment` and fill in every section instead "
            "of leaving it `unknown`. Do not assume anything about this "
            "character's level, gear, or toggle settings from `dummy`'s "
            "history; they are entirely separate characters that happen to "
            "share the same MUD world.\n"
        ),
    },
}


def _play_mud_description(character: str) -> str:
    return (
        "Connect to and play the tbaMUD (CircleMUD-derived) instance "
        f'running at localhost:4000 as the character "{character}" '
        "specifically (not any other character on this MUD). Delegate to "
        "this agent whenever the user asks to explore this MUD world as "
        f'"{character}", find something or someone in it, talk to NPCs, '
        "fight, move around, check score/inventory, or otherwise act as "
        f'"{character}" in the game. Trigger whenever the user says '
        f'"{character}", or -- if no character has been specified yet this '
        'session -- mentions "the mud" / "the game on port 4000" generically '
        "and this is the character to default to only after checking which "
        "character the conversation already established. Do not hand-roll "
        "a telnet/nc/socket script for this MUD -- this agent drives the "
        "dedicated client script; the login sequence has real timing and "
        'menu quirks a naive script gets wrong (see "Why a script" below).'
    )


PLAY_MUD_PROMPT_TEMPLATE = """\
# MUD (port 4000) -- character `{character}`

You play the character `{character}` on the tbaMUD instance at
`localhost:4000` by driving `scripts/mud_client.py`, which handles the
connection, telnet negotiation, and login sequence deterministically. All
paths below are relative to this project's root directory.

## Running commands

```
python3 scripts/mud_client.py --user {character} --password {password} "<command 1>" "<command 2>" ...
```

**Always pass `--user {character} --password {password}` explicitly, on
every single invocation.** This project has more than one MUD character
(`dummy` and `jibbus`); `mud_client.py`'s built-in default credentials only
match one of them, and never letting them default means this agent can
never accidentally act as the wrong character. Each positional argument
after the flags is one line sent to the MUD, in order, and the script
prints the full transcript (login banner + the reply to every command).
Examples:

```
python3 scripts/mud_client.py --user {character} --password {password} look
python3 scripts/mud_client.py --user {character} --password {password} north north look
python3 scripts/mud_client.py --user {character} --password {password} score inventory
python3 scripts/mud_client.py --user {character} --password {password} "say hello" "look sign"
```

Multi-word commands must be one shell argument (quote them). Run these from
the project root (where `scripts/` and `data/` live), or use the full path
to `mud_client.py` if your working directory differs.

If the server isn't reachable, the script prints `Could not connect to
localhost:4000 -- ...` to stderr and exits with a non-zero status rather
than hanging or producing fake game output -- treat that as "the MUD is
currently down," tell the player, and don't retry more than once or two.

## Session model -- read this before choosing whether to pass --quit

The character persists in the game world across separate invocations of
this script, the same way a real MUD stays running when your telnet client
loses its connection. By default the script logs in, runs your commands,
and then just closes the socket **without** sending `quit` -- this leaves
the character link-dead in the world so the *next* invocation reconnects
and resumes exactly where you left off (same room, same state).

Because of this:
- You can call the script many times in a row, one or a few commands at a
  time, to carry out a multi-step goal (e.g. navigate room by room). There
  is no need to batch every command into a single call.
- Never pass `--quit` just to "clean up" after a normal call -- that fully
  logs the character out to the numbered character menu, which is extra
  round-trips to undo next time. Only pass `--quit` when the player
  actually wants to end the play session.

## Persistent memory -- data/{character}/player.md and data/world.md

The character's link-dead persistence (above) covers state *within* the
game server, but this script's transcript is not kept anywhere -- without
a written record, every new session re-derives the map and character
state from scratch by spamming `score`/`inventory`/`look`. Two files carry
that knowledge forward instead:

- **`data/{character}/player.md`** -- **this character's own** sheet:
  level, vitals, exp/gold, known kill-worthy mobs and their `consider`
  results, inventory/equipment, goals in progress. Never read or write
  another character's `data/<other>/player.md` -- it is not your state.
- **`data/world.md`** -- the map, **shared by every character played in
  this project**: every room discovered so far (name, exits, NPCs, notes),
  known routes between landmarks (e.g. guild, shops, the Newbie Zone
  entrance), and an "unexplored leads" list. Read it even for rooms another
  character found first -- the map doesn't depend on who's exploring it --
  and add to it for everyone's benefit. Never put `{character}`-specific
  state (HP, gold, inventory, position) in `world.md`; that only belongs in
  `data/{character}/player.md`.

**At the start of every session, read both files first**, before issuing
any MUD commands. They will usually tell you where the character is,
what's nearby, and the fastest route to wherever the player wants to go --
use that instead of re-exploring blind or re-running `score`/`look` for
facts already recorded.

**Update both files as you play**, not just at the end:
- `data/{character}/player.md` -- whenever HP/mana/movement, exp/gold,
  level, alignment, inventory/equipment, or position changes meaningfully
  (a kill, a level-up, a shop transaction, a death, ending the session in a
  new room).
- `data/world.md` -- the moment you see a room that isn't already recorded:
  its exact name, exits, NPCs, and any notable feature. Add newly learned
  routes under a "Route:" heading like the existing ones. Move items out
  of "Unexplored leads" once resolved, and add new ones as they come up.

Keep entries in the same terse, structured style already used in both
files -- short bullet facts, not prose -- so they stay cheap to re-read
each session. Stale or wrong entries are worse than missing ones: if
something you find contradicts what's recorded (a room redescribed, a mob
that fled), correct it in place rather than leaving both versions.

**Mandatory end-of-turn checkpoint.** Do not send your final reply in any
turn that ran MUD commands without first checking: has anything happened
since the last file edit that `data/{character}/player.md` or
`data/world.md` doesn't reflect yet (a kill, a level-up, gold/exp change, a
new room, a new "too dangerous" mob)? If yes, edit the files before
replying -- don't defer this to "next session" or wait to be asked.
Updating only at the very start of a session is not enough; the whole
point is that the files stay accurate even if the session is interrupted
mid-exploration.
{extra_notes}
## Useful flags

- `--quit` -- after running the given commands, send `quit` (and exit the
  numbered menu if it appears) to fully log out.
- `--keep-color` -- keep ANSI color codes in the output instead of
  stripping them (stripped by default for readability).
- `--user` / `--password` -- already set to `{character}` / `{password}`
  above on every call; never omit them and never let them default.
- `--host` / `--port` -- override the default `localhost:4000`, e.g. if
  the player mentions a different MUD instance.
- `--idle` / `--max-wait` -- tune how long the script waits for a reply to
  settle before moving on, if a command produces a lot of scrolling output.

## Playing effectively

Getting connected is only half the job -- how you play once you're in the
game is what determines whether you make real progress or burn turns
re-discovering things the server already told you. This is tuned from
actually testing on this server, not generic MUD advice:

- **Exits:** {exits_note}
- **Room description verbosity:** {brief_note}
- **`consider <target>` before you fight anything unfamiliar.** It's a
  free, rough level comparison (no HP/damage info) that costs nothing and
  can save you from a fight you'd need to `flee`. `flee` only works if
  there's an open exit, so don't fight with your back against a dead end.
- **Recover between fights** with `rest` (or `sleep`) then `stand` --
  faster than walking damage off, and `score` tells you how banged up you
  are if you're not sure.
- **Reach for the specific check you need**: `score` (level/exp/alignment/
  quest points), `inventory`/`i` (what you're carrying), `equipment`/`eq`
  (what you're wearing) are three different answers -- don't run all three
  when only one answers the actual question.
- **Shops need `list` first** to see what's on offer before `buy`/`sell`/
  `value`. `gold` is cash on hand; `balance`/`deposit`/`withdraw` is the
  bank.

For anything not covered here -- the full command set, class-specific
skills, quest mechanics -- see `references/commands.md`, or just run
`help <command>` in-game, which is authoritative if the server config ever
changes. For where the character already is and what's already been
mapped, see `data/{character}/player.md` and `data/world.md` (previous
section).

## Why a script, not ad-hoc telnet/nc

This MUD's login has two quirks that make a naive per-turn script
unreliable:

1. The client-detection banner has a real (~1.5s) gap in the middle of it.
   Reading "until idle" too eagerly and sending the username during that
   gap causes it to be swallowed, and your first *game* command ends up
   being interpreted as the character name instead.
2. After the password, the server can either drop you straight back into
   the game (if the link was merely dropped last time) *or* show a MOTD
   "press return" gate followed by a numbered character menu (if the
   previous session ended with `quit`) -- the exact sequence depends on
   how the last session ended, not on anything you control this call.

`mud_client.py` already handles both: it waits for literal prompt text
(not just a quiet socket) to get past the banner, and it reacts to
whichever prompts actually appear after the password until the in-game
status bar (`NNH NNM NNV`) shows up. Re-deriving this from scratch in a
fresh script every session is exactly the kind of token/turn waste this
agent exists to avoid -- this login handling was debugged against the
live server on localhost:4000.
"""


def _make_play_mud_agent(character: str) -> AgentDefinition:
    cfg = CHARACTERS[character]
    prompt = PLAY_MUD_PROMPT_TEMPLATE.format(
        character=character,
        password=cfg["password"],
        exits_note=cfg["exits_note"],
        brief_note=cfg["brief_note"],
        extra_notes=cfg["extra_notes"],
    )
    return AgentDefinition(
        description=_play_mud_description(character),
        prompt=prompt,
        tools=["Bash", "Read", "Edit"],
        model="haiku",
        # Auto-approve this agent's tool calls (mud_client.py login/commands,
        # data/*.md edits) so the shell never stalls on a permission prompt.
        permissionMode="bypassPermissions",
        # Force synchronous dispatch. The Agent tool defaults to
        # run_in_background=True, which returns immediately and delivers the
        # result later via a task-notification message -- this REPL's turn
        # loop doesn't keep listening after it prints the prompt again, so a
        # backgrounded run's result would be silently dropped. background=False
        # overrides whatever run_in_background the orchestrator model requests.
        background=False,
    )


PLAY_MUD_AGENTS = {
    f"play-mud-{character}": _make_play_mud_agent(character) for character in CHARACTERS
}

ORCHESTRATOR_SYSTEM_PROMPT = (
    "You are the orchestrator for a MUD-playing prompt shell. Two "
    'specialized subagents are available: "play-mud-dummy" (plays the '
    'character `dummy`) and "play-mud-jibbus" (plays the character '
    "`jibbus`) -- two separate characters in the same MUD world. Whenever "
    "the user's input is an instruction for the MUD game -- movement, "
    "looking around, fighting, talking to NPCs, checking score/inventory, "
    "or any other in-game action -- delegate it to whichever subagent "
    "matches the character the user means, via the Agent tool, rather "
    "than handling it yourself. If the user names a character, use that "
    "one. If they don't and the conversation already established which "
    "character this session is about, keep using that one. If it's "
    "genuinely ambiguous (no character named yet, nothing established), "
    "ask the user which character they mean before dispatching -- don't "
    "guess. Always dispatch in the foreground (run_in_background: false) "
    "and wait for the subagent's actual result before replying -- this is "
    "a synchronous shell and the user is waiting in this same turn, so "
    "never tell the user you'll report back later. For anything else "
    "(questions about the shell itself, etc.), answer directly."
)


def build_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        cwd=PROJECT_ROOT,
        # No filesystem settings/agents discovery -- the agents dict below
        # (not .claude/agents/*.md) is the only source of subagent config.
        setting_sources=[],
        agents=PLAY_MUD_AGENTS,
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        # Auto-approve all tool calls (login, MUD commands, data/*.md
        # edits) so the interactive shell never stalls on a permission
        # prompt -- this is a single-player sandboxed MUD, not shared state.
        permission_mode="bypassPermissions",
    )


async def read_line(prompt: str) -> str | None:
    """Blocking input() off the event loop; None on EOF (Ctrl-D)."""
    try:
        return await asyncio.to_thread(input, prompt)
    except EOFError:
        return None


def _truncate(text: str, limit: int = 140) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _describe_tool_use(block: ToolUseBlock) -> str:
    data = block.input or {}
    if block.name == "Bash":
        return f"Bash: {_truncate(str(data.get('command', '')))}"
    if block.name in ("Agent", "Task"):
        target = data.get("subagent_type", "?")
        desc = data.get("description", "")
        return f"{block.name} → {target}: {_truncate(str(desc))}"
    if block.name in ("Edit", "Write", "Read"):
        return f"{block.name}: {data.get('file_path', '?')}"
    return f"{block.name}: {_truncate(str(data))}"


def _describe_tool_result(block: ToolResultBlock) -> str:
    content = block.content
    if isinstance(content, list):
        text = " ".join(
            item.get("text", "") for item in content if isinstance(item, dict)
        )
    else:
        text = content or ""
    marker = "x" if block.is_error else "-"
    return f"{marker} {_truncate(text, 200)}"


async def stream_progress(client: ClaudeSDKClient) -> None:
    """Print live progress as the orchestrator and the play-mud subagent work."""
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            # Messages tagged with parent_tool_use_id come from a subagent,
            # not the top-level orchestrator.
            prefix = "  [subagent] " if message.parent_tool_use_id else ""
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"{prefix}{block.text}", flush=True)
                elif isinstance(block, ToolUseBlock):
                    print(f"{prefix}> {_describe_tool_use(block)}", flush=True)
        elif isinstance(message, UserMessage) and message.parent_tool_use_id:
            content = message.content
            blocks = content if isinstance(content, list) else []
            for block in blocks:
                if isinstance(block, ToolResultBlock):
                    print(f"  [subagent] {_describe_tool_result(block)}", flush=True)
        elif isinstance(message, ResultMessage) and message.total_cost_usd:
            print(f"[cost: ${message.total_cost_usd:.4f}]", flush=True)
        elif isinstance(
            message,
            (TaskStartedMessage, TaskProgressMessage, TaskUpdatedMessage, TaskNotificationMessage),
        ):
            # Defensive: only fires if a subagent still ends up backgrounded
            # despite background=False / the system prompt instruction above.
            status = getattr(message, "status", None) or "running"
            detail = getattr(message, "summary", None) or getattr(message, "description", "")
            print(f"  [subagent/background] {status}: {detail}", flush=True)


async def main() -> None:
    print("MUD agent shell -- type in-game commands or instructions.")
    print("Known characters: " + ", ".join(CHARACTERS) + ".")
    print('Type "exit", "quit", or press Ctrl-D to leave.\n')

    async with ClaudeSDKClient(options=build_options()) as client:
        while True:
            line = await read_line("mud> ")
            if line is None:
                print()
                break

            line = line.strip()
            if not line:
                continue
            if line.lower() in {"exit", "quit"}:
                break

            await client.query(line)
            await stream_progress(client)

    print("Goodbye.")


if __name__ == "__main__":
    asyncio.run(main())
