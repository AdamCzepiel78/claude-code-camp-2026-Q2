---
name: mud-play
description: Connect to and play the tbaMUD (CircleMUD-derived) instance running at localhost:4000 as the character "dummy". Use this whenever the player asks to explore this MUD world, find something or someone in it, talk to NPCs, fight, move around, check score/inventory, or otherwise act as their character in the game. Make sure to use this skill whenever the user mentions "the mud", "the game on port 4000", "my character dummy", or asks you to look around / walk / interact in that world -- even if they don't say "skill" or name the script directly. Do not hand-roll a telnet/nc/socket script for this MUD -- use the script this skill provides; the login sequence has real timing and menu quirks a naive script gets wrong (see "Why a script" below).
---

# MUD (port 4000)

Plays the character `dummy` on the tbaMUD instance at `localhost:4000` by
driving `scripts/mud_client.py`, which handles the connection, telnet
negotiation, and login sequence deterministically.

## Running commands

```
python3 scripts/mud_client.py "<command 1>" "<command 2>" ...
```

Each positional argument is one line sent to the MUD, in order, and the
script prints the full transcript (login banner + the reply to every
command). Examples:

```
python3 scripts/mud_client.py look
python3 scripts/mud_client.py north north look
python3 scripts/mud_client.py score inventory
python3 scripts/mud_client.py "say hello" "look sign"
```

Multi-word commands must be one shell argument (quote them). Run it from
this skill's directory, or pass the full path to `mud_client.py`.

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

## Persistent memory -- data/player.md and data/world.md

The character's link-dead persistence (above) covers state *within* the
game server, but this script's transcript is not kept anywhere -- without
a written record, every new session re-derives the map and character
state from scratch by spamming `score`/`inventory`/`look`. Two files carry
that knowledge forward instead:

- **`data/player.md`** -- the character sheet: level, vitals, exp/gold,
  known kill-worthy mobs and their `consider` results, inventory/equipment,
  goals in progress.
- **`data/world.md`** -- the map: every room discovered so far (name,
  exits, NPCs, notes), known routes between landmarks (e.g. guild, shops,
  the Newbie Zone entrance), and an "unexplored leads" list.

**At the start of every session, read both files first**, before issuing
any MUD commands. They will usually tell you where the character is,
what's nearby, and the fastest route to wherever the player wants to go --
use that instead of re-exploring blind or re-running `score`/`look` for
facts already recorded.

**Update both files as you play**, not just at the end:
- `player.md` -- whenever HP/mana/movement, exp/gold, level, alignment,
  inventory/equipment, or position changes meaningfully (a kill, a level-up,
  a shop transaction, a death, ending the session in a new room).
- `world.md` -- the moment you see a room that isn't already recorded:
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
since the last file edit that `player.md` or `world.md` doesn't reflect
yet (a kill, a level-up, gold/exp change, a new room, a new "too dangerous"
mob)? If yes, edit the files before replying -- don't defer this to "next
session" or wait to be asked. Updating only at the very start of a session
is not enough; the whole point is that the files stay accurate even if the
session is interrupted mid-exploration.

## Useful flags

- `--quit` -- after running the given commands, send `quit` (and exit the
  numbered menu if it appears) to fully log out.
- `--keep-color` -- keep ANSI color codes in the output instead of
  stripping them (stripped by default for readability).
- `--user` / `--password` -- override the default `dummy` / `helloworld`
  credentials.
- `--host` / `--port` -- override the default `localhost:4000`, e.g. if
  the player mentions a different MUD instance.
- `--idle` / `--max-wait` -- tune how long the script waits for a reply to
  settle before moving on, if a command produces a lot of scrolling output.

## Playing effectively

Getting connected is only half the job -- how you play once you're in the
game is what determines whether you make real progress or burn turns
re-discovering things the server already told you. This is tuned from
actually testing on this server, not generic MUD advice:

- **Exits are already handed to you.** `dummy` has `autoexits` toggled on,
  so every `look` and every move already ends with an `Exits: n e s w`
  style line -- don't spend a separate turn calling `exits` just to see
  what's around; read the line you already have.
- **Don't re-read a room you've already seen this session.** `dummy` plays
  with brief mode off on purpose (room text often hides real gameplay
  hints -- see `help brief` in-game), so the full description shows every
  time you enter. That's a deliberate tradeoff for a human player who
  forgets rooms; you don't forget what's earlier in the transcript, so
  once you have a room's description, move on instead of calling `look`
  again out of habit.
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
mapped, see `data/player.md` and `data/world.md` (previous section).

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
skill exists to avoid -- this login handling was debugged against the
live server on localhost:4000.