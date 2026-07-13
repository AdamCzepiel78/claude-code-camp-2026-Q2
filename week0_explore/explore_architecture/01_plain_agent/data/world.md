# World State

## Midgaard (starting city, zone 30)
- Temple of Midgaard (room 3001) - spawn point for `dummy`.
- Route Temple -> Bakery: south, south, west, west, west, west, west, west, west, north
  (3001 -> 3005 Temple Square -> 3014 Market Square -> 3013 Main Street -> 3009 The Bakery)
  (Simplified from spawn: south, south, west, north gets you Temple(3001)->3005->3014->3013->3009)
- **The Bakery** (room 3009): "You are standing inside the small bakery. A sweet scent of
  danish and fine bread fills the room." Baker NPC present. Exit: south back to Main Street (3013).
  Menu (via `list`):
  | Item | Cost |
  |---|---|
  | A danish pastry | 7 |
  | A bread | 14 |
  | A waybread | 72 |

## Zone 65 (Dwarven Mountain / Kingdom) - DANGEROUS, avoid at low level
- Reached via Laneway (3502, east of Midgaard) -> down -> mountain path.
- Also contains "Granite Head's Bakery" (room 6535, menu: bread 10, danish pastry 5) but it's
  gated behind a PICKPROOF locked door (room 6505 <-> 6513) requiring "a deep green key"
  (obj 6515) carried by a dwarf guard (mob 6500) stationed at 6505. Zone flagged "above your
  recommended level" with multiple guards. Not worth pursuing for a low-level character when
  the Midgaard bakery is easily reachable.
- Note: static preview JSON at week0_explore/preview/data/world/wld/65.json has an incorrect/
  stale BFS-exit graph that doesn't match the live server (built fresh from
  week0_explore/infrastructure/lib/world/*.wld via the tbamud master branch clone in Docker).
  Trust the raw .wld files in infrastructure/lib/world/ over the preview JSON for zone 65.

## Connection notes
- Login sequence: send name -> "Password:" -> send password -> if new session, "*** PRESS
  RETURN:" then blank line -> character menu -> "1" to enter game. If character was already
  connected/linkless, server sends "Reconnecting." and drops you straight back into the game
  at wherever you last were (skip the menu entirely).
- Movement commands must be sent one at a time and awaited (wait for the status-bar prompt
  regex `\d+H \d+M \d+V.*>` ) before sending the next command, otherwise responses can
  interleave/misalign and produce apparent "desync".
