is the 

# World map — tbaMUD @ localhost:4000

Persistent memory of places `dummy` has discovered. **Read at session start**
and **append/update whenever a new room, exit, NPC, or landmark is found.**
Record each room by its exact name, its exits, and anything notable.

_Last updated: 2026-07-16_

> **This world is Midgaard** (the standard CircleMUD/tbaMUD city). Main Street
> runs east–west through Market Square; the guilds branch off it.

## Known objectives / landmarks sought

- **Warrior Guild** — ✅ FOUND. It is the **Guild of Swordsmen**, entered by
  going **south off eastern Main Street** (the room whose north side has the
  weapon shop). Warriors here are "swordsmen"; dummy's title is "Swordpupil".

## Key gameplay note — movement regen needs a LIVE connection

Movement points (and presumably HP/mana) **only regenerate while the character
is actually connected**. Because `mud_client.py` disconnects after each call,
a link-dead character sitting between calls does NOT regen — waiting real time
between invocations does nothing. To refill movement, hold ONE connection open
across a regen tick, e.g. `sleep` then a long run of filler commands in a
single invocation:
`python3 scripts/mud_client.py sleep wait wait ... (≈250×) score`
(~100s connected ≈ one MUD-hour tick ≈ +14 move while sleeping). `dummy` is
hungry+thirsty, which throttles regen further — curing that (find a fountain:
`drink fountain`, or food) should speed it up.

## Route: The Levee → Warrior Guild

Levee →n→ Dark Alley At The Levee →w→ Dark Alley (mercenary) →w→ Common Square
→n→ Market Square →e→ Main Street (gen. store/pet shop) →e→ Main Street (weapon
shop) →s→ **Guild of Swordsmen entrance hall**.

## Rooms discovered

### The Levee  _(starting room)_

- **Exits:** n, s
- **NPC:** Captain Stolar (sells boats)
- **Notes:** south is the river — "You need a boat to go there."

### The Dark Alley At The Levee  _(n of The Levee)_

- **Exits:** e, s, w
- **NPC:** a cityguard
- **Notes:** s → The Levee; w → the inner-city Dark Alley.

### The Eastern End Of The Alley  _(e of The Dark Alley At The Levee)_

- **Exits:** s, w
- **Notes:** city wall blocks further east; warehouse is south.

### The Deserted Warehouse  _(s of The Eastern End)_

- **Exits:** n
- **NPC:** a sailor ("waiting to help you")
- **Notes:** decorated with old ship items.

### The Dark Alley  _(w of The Dark Alley At The Levee)_

- **Exits:** e, s, w
- **NPC:** a mercenary ("waiting for a job")
- **Notes:** w → Common Square; s → **Guild of Thieves**; e → back toward levee.

### The Common Square  _(w of The Dark Alley)_

- **Exits:** n, e, s, w
- **NPCs:** a beastly fido; "an odif yltsaeb" (walks backwards)
- **Notes:** n → Market Square; w → poor alley; s → "a nasty smell"; e → Dark Alley.

### Market Square  _(n of Common Square)_ — "the famous Square of Midgaard"

- **Exits:** n, e, s, w
- **Notes:** statue in the middle; n → temple square; s → common square;
  e & w → Main Street.

### Main Street (west end)  _(e of Market Square)_

- **Exits:** n, e, s, w
- **Notes:** n → general store; s → Pet Shop; w → Market Square; e → continues.

### Main Street (east end)  _(e of Main Street west end)_

- **Exits:** n, e, s, w
- **NPCs:** a Peacekeeper; a beastly fido
- **Notes:** n → weapon shop; **s → Guild of Swordsmen (Warrior Guild)**;
  e → leave town; w → Market Square.

### The Entrance Hall To The Guild Of Swordsmen  _(s of Main Street east end)_ ⚔️ **WARRIOR GUILD**

- **Exits:** n, e
- **NPCs:** a knight (guards the entrance); a cityguard
- **Features:** an ATM (automatic teller machine) in the wall
- **Notes:** n → Main Street; e → the bar. "A place where one has to be careful
  not to say something wrong (or right)." NOT where you practice — the
  guildmaster is deeper in (bar → yard).

### The Bar Of Swordsmen  _(e of the entrance hall)_

- **Exits:** s, w
- **NPCs:** a waiter
- **Features:** a sociable bulletin board on the wall
- **Notes:** s → the practice yard; w → entrance hall.

### The Tournament And Practice Yard  _(s of the bar)_ 🎯 **PRACTICE HERE**

- **Exits:** n, d (down)
- **NPC:** **Your guildmaster** (sharpening an axe) — use `practice <skill>` here.
- **Features:** a well leading down into darkness.
- **Notes:** n → the bar. This is the room where warrior skills are learned;
  `practice` elsewhere gives "You can only practice skills in your guild."

### The Weapon Shop  _(n of Main Street east end)_ 🗡️ **SHOP**

- **Exits:** s (back to Main Street)
- **NPCs:** a weaponsmith (shopkeeper — `list` / `buy <item>`); a Peacekeeper
- **Features:** a note on the counter; room packed with weaponry to the ceiling.
- **Notes:** From Market Square: e → e → n. Need gold to buy (currently 0).

### Main Street (west of market)  _(w of Market Square)_

- **Exits:** n, e, s, w
- **NPC:** a Peacekeeper
- **Notes:** n → the Bakery; s → the Armory entrance; e → Market Square; w → continues.

### The Bakery  _(n of Main Street west-of-market)_ 🍞 **SHOP (food → cures hunger)**

- **Exits:** s (back to Main Street)
- **NPC:** the baker (shopkeeper — `list` / `buy bread`)
- **Features:** a sign on the counter; shelves of bread & danish.
- **Notes:** From Market Square: w → n. Buying bread here cures hunger (helps
  movement regen). Need gold (currently 0).

### The Armory  _(s of Main Street west-of-market)_ 🛡️ **SHOP (armor)**

- **Exits:** n (back to Main Street)
- **NPC:** an armorer (shopkeeper — sells new & used armor)
- **Features:** a note on the wall; helmets, shields, suits of armor on display.
- **Notes:** From Market Square: w → s. Directly opposite the Bakery. Need gold.

### Temple Square  _(n of Market Square)_

- **Exits:** (at least) n → Temple of Midgaard, s → Market Square.
- **Notes:** the square below the temple steps; passed through en route to the temple.

### The Temple Of Midgaard  _(n of Temple Square / up the steps)_ ⛪ **RECALL POINT**

- **Exits:** n, e, s, w, d
- **Features:** an ATM in the wall; the **donation room** in an alcove to the
  **east** (free gear/coin dropped by other players — good newbie source); the
  **Reading Room** to the **west**; steps lead **down (d)** to Temple Square.
- **Notes:** From Market Square: n → n. Standard Midgaard recall/reset point.

### By The Temple Altar  _(n of Temple of Midgaard)_

- **Exits:** n, s
- **Features:** a huge white marble altar; a 10-foot statue of **Odin**.
- **Notes:** n → steps out the back of the temple toward the countryside.

### Behind The Temple Altar  _(n of the altar)_

- **Exits:** n, s
- **Notes:** a dirt path leaving the temple; n continues into countryside toward
  the **Dragonhelm Mountains** (far north).

### The Great Field Of Midgaard  _(n of Behind The Temple Altar)_ 🌾 **COUNTRYSIDE**

- **Exits:** n, s
- **Notes:** open field; city of Midgaard is south, path continues north.
  Countryside/wilderness begins here — likely where low-level mobs (exp/gold) are.

### The Midgaard Donation Room  _(e of Temple of Midgaard)_

- **Exits:** w (back to Temple)
- **NPC:** "a very kind and caring soul"
- **Notes:** Holds only items other players donate — **was EMPTY** on 2026-07-15
  (no bread/water/anything). Not a reliable food/water source. Wooden benches.

### The Great Field Of Midgaard (#2)  _(n of the first Great Field)_

- **Exits:** n, e, s, w
- **Notes:** "a strange structure on the eastern side of the path"; a small dirt
  path splits off **west**. Both unexplored.

### The Entrance To The Newbie Zone  _(e of Great Field #2)_ 🐣 **NEWBIE ZONE ENTRANCE**

- **Exits:** n (into the newbie zone), w (back to Great Field #2)
- **NPC:** "the newbie monster" — a scripted easy first kill ("Kill him! Kill him!")
- **Notes:** This IS the "strange structure" east of Great Field #2. Enter **north**
  when ready. Great spot to try `kick` and earn starter exp/gold.
- **Route from Temple:** n → n → n → n (to Great Field #2) → e.

### The Great Field Of Midgaard (#3, north dead-end)  _(n of Great Field #2)_

- **Exits:** s only
- **Notes:** "the way north appears to be blocked by a large plot device" —
  deliberate dead-end; northern extent of this path.

## Newbie Zone (inside — enter N from the entrance)

A maze of slimy, untidy hallways. Doors shown in (parens) are **closed** and
lead to challenge rooms (unopened so far). Weak mobs scattered throughout: a
loose "little pet dragon", "creepy little crawling things", and several scripted
"newbie monster" easy kills — good `kick` practice + starter exp/gold.

### The Beginning Of The Passage  _(n of the Newbie Zone entrance)_

- **Exits:** e, s (back to entrance)
- **NPC:** a little pet dragon (loose, sniffing about)

### The Dirty Hallway  _(e of The Beginning Of The Passage)_

- **Exits:** e, s (door — was closed, **opened** with `open door`), w
- **NPCs seen:** a creepy little crawling thing; the loose little pet dragon
  passes through here too (SKIP — too dangerous, see player.md).
- Combat keyword for the crawling thing is **`crawler`**, not "crawling thing"
  (that phrase gives "Consider killing who?").

### A Small Room  _(s of The Dirty Hallway, through the door)_ — NEW 2026-07-16

- **Exits:** n, (e) closed door, (d) closed/grated — a well down with a
  "rather secure grate covering it" (can't descend, at least not yet).
- **NPCs:** a creepy little crawling thing (`crawler`, consider = "perfect
  match"); **The Newbie Guard** (consider = "You would need a lot of luck!" —
  a step up from the newbie monster, treat as risky, rest to full before
  trying).

### A Nexus  _(e of The Dirty Hallway)_ — intersection

- **Exits:** n, e, s, w — both doors opened 2026-07-16 (were closed).
- **Notes:** passages "brighten" north & east; dark hallway continues south.
  A crawling thing here. n → A Bright Hallway; e → unexplored (not yet
  entered — "the passage brightens" to the east too, may be similar/same).

### A Bright Hallway  _(n of A Nexus)_ — NEW 2026-07-16

- **Exits:** n, s
- **Notes:** clean, decorated, unlike the rest of the zone; "an interesting
  design on the floor" (unexamined). NPC: a newbie monster spawns here
  (killed, 140 exp + 20 gold + a shiny newbie dagger). North is unexplored.

### More Of The Hallway  _(s of A Nexus, ALSO = e of A Small Room)_

- **Exits:** n, s, w — the (w) door connects back to A Small Room; the maze
  loops together here, confirmed 2026-07-16.
- **NPC:** a newbie monster ("Kill him!") — killed cleanly, 149 exp + 20 gold
  + a shiny newbie dagger.

### Another Corner  _(s of More Of The Hallway)_

- **Exits:** n, e, w — the (e) door (opened 2026-07-16) leads to **The
  Alchemist's Room**.
- **NPC:** a newbie monster sometimes present ("Kill him!").

### The Alchemist's Room  _(e of Another Corner)_ ⚠️ **TOUGHER SUB-AREA — NEW 2026-07-16**

- **Exits:** (n) closed door (unexplored), w, d (stairway down).
- **Sign by the stairs:** "If you are below level 7 and alone, or below level
  4 then bugger off! Or else don't blame me if you die..." — the down stairs
  lead somewhere meaningfully harder than the rest of the Newbie Zone.
- **NPCs:**
  - **the zombiefied newbie** — AGGRESSIVE, attacks automatically on entry, no
    `kill` needed. Hits harder than anything else fought so far (took a lvl-1
    character from 22→14 HP). Worth it though: 737 exp + level-up + 40 gold.
  - 2× **a funny little imp-like thing (a quasit perhaps?)** — consider = "a
    lot of luck!", not yet fought.
  - **The Newbie Alchemist** — consider = "a lot of luck and great equipment!",
    skip.
- **Notes:** did not descend the (d) stairway yet — sign suggests wait until
  level 4+ and not alone.

### Newbie Zone unexplored

- (e) and (d) off A Small Room (the (d) is grated/locked, may need a key or
  a strength/tool check).
- (e) off the Nexus; (n) off A Bright Hallway; (n) off The Alchemist's Room;
  the (d) stairway down from The Alchemist's Room (level 4+/7+ per the sign).
- West from Another Corner; the hallway grid likely loops further.

## Southwest quarter — Poor Alley → Wall Road → Concourse → Road Crossing — NEW 2026-07-16

Discovered while backtracking; connects Common Square to a second road-cross
hub on the far side of the city.

**Route:** Common Square →w→ Eastern End Of Poor Alley (fido spot) →w→ Poor
Alley (a beggar, harmless — consider="perfect match" but not worth killing)
→w→ Wall Road (letters on the wall) →s→ Wall Road (2) →s→ On The Bridge (river
below) →s→ NW End Of The Concourse →s→ On The Concourse (SW corner) →e→ On The
Concourse (E/W) →n→ Emerald Avenue →n→ Emerald Avenue (bend) →e→ Emerald Avenue
(bend, a cityguard) →n→ **The Road Crossing** (2nd hub — road sign, chain to
the sky) →e→ Park Road (bend).

- **The Road Crossing:** exits n e s w u. Sign: N/S = Emerald Avenue, E/W =
  Park Road, **Up = Redferne's Flying Citadel** (unexplored, likely high-level).
- **On The Concourse (SW corner) →w→ The South Gate:** "This zone is above
  your recommended level" warning fires here — leads to the **forest of
  Miden'Nir**. AVOID at level 1.
- No `recall` command exists for this character — this whole route must be
  walked to get back to Market Square/Temple (~13 moves one-way from Park
  Road to Common Square, confirmed 2026-07-16).

## Countryside route (city → open field)

Temple of Midgaard →n→ By The Temple Altar →n→ Behind The Temple Altar →n→
Great Field #1 →n→ Great Field #2 (structure E, path W) →n→ Great Field #3
(north blocked, dead-end).

## Unexplored leads

- Great Field #2: the side path **west** (the eastern "strange structure" is
  the Newbie Zone entrance — ✅ found).
- ✅ Fountain found: **Temple Square** (`drink fountain` cures thirst). Gold is
  no longer 0 (110 on hand as of 2026-07-16, after the Newbie Zone run) —
  bakery/armory purchases now affordable, not yet done.
- Newbie Zone: several closed doors still unopened (see Newbie Zone section
  above); the grated well in A Small Room; whether to risk the 2 quasits in
  The Alchemist's Room; the (d) stairway there (level 4+/7+ warning).
- Road Crossing "Up" exit → Redferne's Flying Citadel — unexplored, unknown
  level requirement.
- Reading Room (w of Temple); n and further exits from the Temple.
- Main Street continues further west (w of Main Street west-of-market).
- ✅ Poor alley — explored, see Southwest quarter section.
- The "nasty smell" (s of Common Square) — still unexplored (likely sewers).
- Guild of Thieves (s of the inner Dark Alley).
- The bar (e of the Guild of Swordsmen entrance).
- East out of town (e of eastern Main Street).
