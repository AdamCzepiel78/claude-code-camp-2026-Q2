# tbaMUD command reference (localhost:4000, character `dummy`)

Verified live against the running server (`commands`, `toggle`, and the
relevant `help <topic>` entries) rather than assumed from generic DikuMUD
docs, so this matches how this specific instance is actually configured.

## Movement

`n`/`north`, `s`/`south`, `e`/`east`, `w`/`west`, `ne`/`northeast`,
`nw`/`northwest`, `se`/`southeast`, `sw`/`southwest`, `u`/`up`, `d`/`down`,
`enter <portal/building>`, `leave` (reverse of enter).

## Orientation and info

- `look` (`l`) -- full room description. Always available even in brief
  mode; `dummy` has brief mode off anyway (see below).
- `look <target>` / `examine <target>` -- inspect something specific.
- `exits` -- listed automatically after every `look`/move for this
  character (autoexits is on), so you rarely need to call it directly.
- `scan` -- peek into adjacent rooms without moving.
- `where` -- other players/mobs in your zone.
- `areas` -- list of zones on the MUD.
- `map` -- disabled on this server, don't rely on it.

## Checking yourself

- `score` (`sc`) -- level, HP/mana/move, AC, alignment, exp, gold, quest
  points, title.
- `inventory` (`i`) -- what you're carrying.
- `equipment` (`eq`) -- what you're wearing/wielding.
- `practice` (with no target, outside a guild) -- lists all skills/spells
  you know and your proficiency. At a guildmaster, `practice <skill>`
  trains it.
- `whoami`, `title`, `levels` -- identity/leveling info.

## Communication

`say <msg>`, `tell <name> <msg>`, `ask <name> <question>`, `whisper`,
`emote`/`gemote`, `socials` (list of canned social commands like `smile`),
`gossip`/`gsay`, `shout`, `holler`, `group`/`gtell` (group-only chat).

## Combat

- `consider <target>` -- rough level comparison before engaging. Free,
  imprecise (no HP/damage info), and worth doing before fighting anything
  unfamiliar.
- `hit`/`kill <target>` -- attack.
- `flee` -- attempt to escape combat. Only works if a free exit exists, so
  don't fight yourself into a corner.
- `assist <name>` -- join a group member's fight (or `autoassist` to do it
  automatically while grouped).
- `diagnose <target>` -- check someone's health without a full `look`.
- `rest`, `sleep`, `stand`, `wake` -- recover HP/mana between fights; you
  need to `stand` back up before you can act again.
- `backstab`, `steal`, `hide`, `sneak`, `track` -- class/skill-dependent
  actions, availability depends on your class and practiced skills.

## Economy

- `list` -- see a shopkeeper's wares (must be in a shop room).
- `buy`/`sell`/`value <item>` -- trade with the current shopkeeper.
- `gold` -- cash on hand. `balance`/`deposit`/`withdraw` -- bank balance.
- `split`/`autosplit` -- share gold with a group.
- `donate`/`junk` -- get rid of items.

## Quests

- `quests` -- list/manage quests. (`quest` singular doesn't resolve to
  anything -- the server suggests `quests` or `quit` if you typo it.)

## Toggles already set for `dummy`

Check anytime with `toggle` (no argument) -- current relevant state:

| Toggle | State | Why it matters |
|---|---|---|
| AutoExits | ON | Exits line appears after every `look`/move -- don't also call `exits`. |
| AutoLoot | ON | Corpses are looted automatically after a kill. |
| Compact | ON | Suppresses the extra blank line after each command. |
| Brief | OFF | Full room descriptions show every visit -- deliberately left off, see `help brief`: descriptions "frequently... contain small but vital hints." |

Don't flip these without a reason -- they're already tuned for a good
signal-to-noise ratio.

## Full raw list (`commands` in-game, for anything not covered above)

```
'          cast       follow     junk       offer      south      toggle
:          check      get        kill       order      say        track
afk        close      gemote     kick       put        sacrifice  typo
alias      clear      give       look       page       save       up
areas      cls        gold       leave      pick       score      unfollow
assist     commands   gossip     levels     policy     scan       unlock
ask        compact    group      list       pour       se         use
astat      consider   grab       lock       practice   sell       value
auction    credits    grats      mail       prefedit   shout      version
autoassist down       gsay       map        prompt     sit        visible
autodoor   deposit    gtell      motd       qsay       sip        west
autoexits  diagnose   help       north      quaff      sleep      wake
autogold   display    happyhour  ne         quest      sneak      wear
autokey    donate     hide       news       qui        socials    weather
autoloot   drink      hindex     noauction  quit       southeast  who
automap    drop       history    nogossip   reply      southwest  where
autosac    east       hit        nograts    read       split      whirlwind
autosplit  eat        hold       norepeat   receive    stand      whisper
backstab   emote      holler     northeast  recite     steal      whoami
balance    enter      house      northwest  remove     sw         whois
bandage    equipment  inventory  noshout    rent       tell       wield
brief      examine    idea       notell     rest       taste      wizlist
buy        fill       immlist    nw         rescue     time       write
bug        flee       info       open       return     title
```

Any command not explained above: run `help <command>` in-game -- it works
for all of these and is more authoritative than this file if the server
config ever changes.
