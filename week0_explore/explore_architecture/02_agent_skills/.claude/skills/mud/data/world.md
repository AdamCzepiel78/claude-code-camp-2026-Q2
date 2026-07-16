# World map — tbaMUD @ localhost:4000

Persistent memory of places `dummy` has discovered. **Read at session start**
and **append/update whenever a new room, exit, NPC, or landmark is found.**
Record each room by its exact name, its exits, and anything notable.

_Last updated: 2026-07-15_

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
- **Exits:** e, (s) closed door — noises behind it, w
- **NPC:** a creepy little crawling thing

### A Nexus  _(e of The Dirty Hallway)_ — intersection
- **Exits:** (n) closed door, (e) closed door, s, w
- **Notes:** passages "brighten" north & east (behind the closed doors); dark
  hallway continues south. A crawling thing here.

### More Of The Hallway  _(s of A Nexus)_
- **Exits:** n, s, (w) closed door
- **NPC:** a newbie monster ("Kill him!")

### Another Corner  _(s of More Of The Hallway)_
- **Exits:** n, (e) closed door, w
- **NPC:** a newbie monster ("Kill him!")

### Newbie Zone unexplored
- All the closed doors: (s) off Dirty Hallway; (n)/(e) off the Nexus;
  (w) off More Of The Hallway; (e) off Another Corner.
- West from Another Corner; the hallway grid likely loops further.

## Countryside route (city → open field)
Temple of Midgaard →n→ By The Temple Altar →n→ Behind The Temple Altar →n→
Great Field #1 →n→ Great Field #2 (structure E, path W) →n→ Great Field #3
(north blocked, dead-end).

## Unexplored leads
- Great Field #2: the "strange structure" to the **east**, and the side path **west**.
- Still need to fix hunger/thirst + 0 gold: donation room was empty, bakery needs
  gold, no fountain found yet. Option: kill a weak mob (fido/blob in the squares)
  with `kick` for coin, then buy bread/water.
- Reading Room (w of Temple); n and further exits from the Temple.
- Main Street continues further west (w of Main Street west-of-market).
- Poor alley (w of Common Square); the "nasty smell" (s of Common Square).
- Guild of Thieves (s of the inner Dark Alley).
- Temple Square & Temple of Midgaard (n of Market Square) — usual recall point.
- The bar (e of the Guild of Swordsmen entrance).
- East out of town (e of eastern Main Street).
