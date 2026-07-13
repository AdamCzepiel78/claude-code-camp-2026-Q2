from enum import IntEnum, IntFlag


class ObjectType(IntEnum):
    """Object type flags."""
    LIGHT = 1  # Item is a light source.
    SCROLL = 2  # Item is a magical scroll.
    WAND = 3  # Item is a magical wand.
    STAFF = 4  # Item is a magical staff.
    WEAPON = 5  # Item is a weapon.
    FIREWEAPON = 6  # Currently not implemented.  Do not use.
    MISSILE = 7  # Currently not implemented.  Do not use.
    TREASURE = 8  # Item is treasure other than gold coins (e.g. gems).
    ARMOR = 9  # Item is armor.
    POTION = 10  # Item is a magical potion.
    WORN = 11  # Currently not implemented.  Do not use.
    OTHER = 12  # Miscellaneous object with no special properties.
    TRASH = 13  # Trash -- junked by cleaners, not bought by shopkeepers.
    TRAP = 14  # Currently not implemented.  Do not use.
    CONTAINER = 15  # Item is a container.
    NOTE = 16  # Item is a note (can be written on).
    DRINKCON = 17  # Item is a drink container.
    KEY = 18  # Item is a key.
    FOOD = 19  # Item is food.
    MONEY = 20  # Item is money (gold coins).
    PEN = 21  # Item is a pen.
    BOAT = 22  # Item is a boat; allows you to traverse SECT_WATER_NOSWIM.
    FOUNTAIN = 23  # Item is a fountain.


class ObjectExtraEffect(IntFlag):
    """Object extra effects (bitvector)."""
    GLOW = 1  # Item is glowing (cosmetic).
    HUM = 2  # Item is humming (cosmetic).
    NORENT = 4  # Item cannot be rented.
    NODONATE = 8  # Item cannot be donated.
    NOINVIS = 16  # Item cannot be made invisible.
    INVISIBLE = 32  # Item is invisible.
    MAGIC = 64  # Item has a magical aura and can't be enchanted.
    NODROP = 128  # Item is cursed and cannot be dropped.
    BLESS = 256  # Item is blessed (cosmetic).
    ANTI_GOOD = 512  # Item can't be used by good-aligned characters.
    ANTI_EVIL = 1024  # Item can't be used by evil-aligned characters.
    ANTI_NEUTRAL = 2048  # Item can't be used by neutrally-aligned characters.
    ANTI_MAGIC_USER = 4096  # Item can't be used by the Mage class.
    ANTI_CLERIC = 8192  # Item can't be used by the Cleric class.
    ANTI_THIEF = 16384  # Item can't be used by the Thief class.
    ANTI_WARRIOR = 32768  # Item can't be used by the Warrior class.
    NOSELL = 65536  # Shopkeepers will not buy or sell the item.
    QUEST = 131072  # Item is a quest item (tbaMUD).


class ObjectWear(IntFlag):
    """Object wear flags (bitvector)."""
    WEAR_TAKE = 1  # Item can be taken (picked up off the ground).
    WEAR_FINGER = 2  # Item can be worn on the fingers.
    WEAR_NECK = 4  # Item can be worn around the neck.
    WEAR_BODY = 8  # Item can be worn on the body.
    WEAR_HEAD = 16  # Item can be worn on the head.
    WEAR_LEGS = 32  # Item can be worn on the legs.
    WEAR_FEET = 64  # Item can be worn on the feet.
    WEAR_HANDS = 128  # Item can be worn on the hands.
    WEAR_ARMS = 256  # Item can be worn on the arms.
    WEAR_SHIELD = 512  # Item can be used as a shield.
    WEAR_ABOUT = 1024  # Item can be worn about the body.
    WEAR_WAIST = 2048  # Item can be worn around the waist.
    WEAR_WRIST = 4096  # Item can be worn around the wrist.
    WEAR_WIELD = 8192  # Item can be wielded; e.g. weapons.
    WEAR_HOLD = 16384  # Item can be held (the 'hold' command).


class ObjectAffectLocation(IntEnum):
    """Object affect location flags."""
    NONE = 0  # No effect (typically not used).
    STR = 1  # Apply to strength.
    DEX = 2  # Apply to dexterity.
    INT = 3  # Apply to intelligence.
    WIS = 4  # Apply to wisdom.
    CON = 5  # Apply to constitution.
    CHA = 6  # Apply to charisma.
    CLASS = 7  # Unimplemented.  Do not use.
    LEVEL = 8  # Unimplemented.  Do not use.
    AGE = 9  # Apply to character's MUD age, in MUD years.
    CHAR_WEIGHT = 10  # Apply to weight.
    CHAR_HEIGHT = 11  # Apply to height.
    MANA = 12  # Apply to MAX mana points.
    HIT = 13  # Apply to MAX hit points.
    MOVE = 14  # Apply to MAX movement points.
    GOLD = 15  # Unimplemented.  Do not use.
    EXP = 16  # Unimplemented.  Do not use.
    AC = 17  # Apply to armor class (AC).
    HITROLL = 18  # Apply to hitroll.
    DAMROLL = 19  # Apply to damage roll bonus.
    SAVING_PARA = 20  # Apply to save throw: paralyze
    SAVING_ROD = 21  # Apply to save throw: rods
    SAVING_PETRI = 22  # Apply to save throw: petrif
    SAVING_BREATH = 23  # Apply to save throw: breath
    SAVING_SPELL = 24  # Apply to save throw: spells


class RoomFlag(IntFlag):
    """Room flags (bitvector)."""
    DARK = 1  # Room is dark.
    DEATH = 2  # Room is a death trap; char 'dies' (no xp lost).
    NOMOB = 4  # MOBs (monsters) cannot enter room.
    INDOORS = 8  # Room is indoors.
    PEACEFUL = 16  # Room is peaceful (violence not allowed).
    SOUNDPROOF = 32  # Shouts, gossips, etc. won't be heard in room.
    NOTRACK = 64  # 'track' can't find a path through this room.
    NOMAGIC = 128  # All magic attempted in this room will fail.
    TUNNEL = 256  # Only one person allowed in room at a time.
    PRIVATE = 512  # Cannot teleport in or GOTO if two people here.
    GODROOM = 1024  # Only LVL_GOD and above allowed to enter.
    HOUSE = 2048  # Reserved for internal use. Do not set.
    HOUSE_CRASH = 4096  # Reserved for internal use. Do not set.
    ATRIUM = 8192  # Reserved for internal use. Do not set.
    OLC = 16384  # Reserved for internal use. Do not set.
    BFS_MARK = 32768  # Reserved for internal use. Do not set.
    WORLDMAP = 65536  # World-map style maps here (tbaMUD).


class RoomSectorType(IntEnum):
    """Room sector types."""
    INSIDE = 0  # Indoors (small number of move points needed).
    CITY = 1  # The streets of a city.
    FIELD = 2  # An open field.
    FOREST = 3  # A dense forest.
    HILLS = 4  # Low foothills.
    MOUNTAIN = 5  # Steep mountain regions.
    WATER_SWIM = 6  # Water (swimmable).
    WATER_NOSWIM = 7  # Unswimmable water - boat required for passage.
    FLYING = 8  # Wheee!
    UNDERWATER = 9  # Underwater.


class RoomDoorFlag(IntEnum):
    """Room door flags."""
    NO_DOOR = 0
    DOOR = 1
    PICKPROOF = 2


class MobAction(IntFlag):
    """Mob action flags (bitvector)."""
    SPEC = 1
    # This flag must be set on mobiles which have special procedures
    # written in C.  In addition to setting this bit, the procedure must be
    # assigned in spec_assign.c, and the specproc itself must (of course)
    # must be written.  See the section on Special Procedures in the file
    # coding.doc for more information.
    SENTINEL = 2
    # Mobiles wander around randomly by default; this bit should be set
    # for mobiles which are to remain stationary.
    SCAVENGER = 4
    # The mob should pick up valuables it finds on the ground.  More
    # expensive items will be taken first.
    ISNPC = 8  # Reserved for internal use. Do not set.
    AWARE = 16
    # Set for mobs which cannot be backstabbed. Replaces the
    # ACT_NICE_THIEF bit from Diku Gamma.
    AGGRESSIVE = 32
    # Mob will hit all players in the room it can see. See also the WIMPY bit.
    STAY_ZONE = 64
    # Mob will not wander out of its own zone -- good for keeping your mobs
    # as only part of your own area.
    WIMPY = 128
    # Mob will flee when being attacked if it has less than 20% of its hit
    # points.  If the WIMPY bit is set in conjunction with any of
    # the forms of the AGGRESSIVE bit, the mob will only attack
    # mobs that are unconscious (sleeping or incapacitated).
    AGGR_EVIL = 256  # Mob will attack players that are evil-aligned.
    AGGR_GOOD = 512  # Mob will attack players that are good-aligned.
    AGGR_NEUTRAL = 1024  # Mob will attack players that are neutrally aligned.
    MEMORY = 2048
    # Mob will remember the players that initiate attacks on it, and
    # initiate an attack on that player if it ever runs into him again.
    HELPER = 4096
    # The mob will attack any player it sees in the room that is fighting
    # with a mobile in the room. Useful for groups of mobiles that travel
    # together; i.e. three snakes in a pit, to force players to fight all
    # three simultaneously instead of picking off one at a time.
    NOCHARM = 8192  # Mob cannot be charmed.
    NOSUMMON = 16384  # Mob cannot be summoned.
    NOSLEEP = 32768  # Sleep spell cannot be cast on mob.
    NOBASH = 65536  # Large mobs such as trees that cannot be bashed.
    NOBLIND = 131072  # Mob cannot be blinded.
    NOKILL = 262144  # Mob cannot be attacked (tbaMUD; stock Circle used this bit internally as NOTDEADYET).


class MobAffect(IntFlag):
    """Mob affect flags (bitvector)."""
    BLIND = 1  # Mob is blind.
    INVISIBLE = 2  # Mob is invisible.
    DETECT_ALIGN = 4  # Mob is sensitive to the alignment of others.
    DETECT_INVIS = 8  # Mob can see invisible characters and objects.
    DETECT_MAGIC = 16  # Mob is sensitive to magical presence.
    SENSE_LIFE = 32  # Mob can sense hidden life.
    WATERWALK = 64  # Mob can traverse unswimmable water sectors.
    SANCTUARY = 128  # Mob is protected by sanctuary (half damage).
    GROUP = 256  # Reserved for internal use. Do not set.
    CURSE = 512  # Mob is cursed.
    INFRAVISION = 1024  # Mob can see in dark.
    POISON = 2048  # Reserved for internal use. Do not set.
    PROTECT_EVIL = 4096  # Mob is protected from evil characters. No effect at present.
    PROTECT_GOOD = 8192  # Mob is protected from good characters. No effect at present.
    SLEEP = 16384  # Reserved for internal use. Do not set.
    NOTRACK = 32768  # Mob cannot be tracked.
    UNUSED16 = 65536  # Unused (room for future expansion).
    UNUSED17 = 131072  # Unused (room for future expansion).
    SNEAK = 262144  # Mob can move quietly (room not informed).
    HIDE = 524288  # Mob is hidden (only visible with sense life).
    UNUSED20 = 1048576  # Unused (room for future expansion).
    CHARM = 2097152  # Reserved for internal use. Do not set.


class TbaMobAffect(IntFlag):
    """Mob affect flags in tbaMUD's 128-bit numbering.

    tbaMUD's conversion to bit arrays inserted DONTUSE at bit 0,
    shifting every classic AFF_* flag up by one bit relative to
    stock CircleMUD (see MobAffect).
    """
    DONTUSE = 1  # Placeholder so 0 means "no bits set". Do not set.
    BLIND = 2  # Mob is blind.
    INVISIBLE = 4  # Mob is invisible.
    DETECT_ALIGN = 8  # Mob is sensitive to the alignment of others.
    DETECT_INVIS = 16  # Mob can see invisible characters and objects.
    DETECT_MAGIC = 32  # Mob is sensitive to magical presence.
    SENSE_LIFE = 64  # Mob can sense hidden life.
    WATERWALK = 128  # Mob can traverse unswimmable water sectors.
    SANCTUARY = 256  # Mob is protected by sanctuary (half damage).
    GROUP = 512  # Reserved for internal use. Do not set.
    CURSE = 1024  # Mob is cursed.
    INFRAVISION = 2048  # Mob can see in dark.
    POISON = 4096  # Reserved for internal use. Do not set.
    PROTECT_EVIL = 8192  # Mob is protected from evil characters.
    PROTECT_GOOD = 16384  # Mob is protected from good characters.
    SLEEP = 32768  # Reserved for internal use. Do not set.
    NOTRACK = 65536  # Mob cannot be tracked.
    FLYING = 131072  # Mob is flying.
    SCUBA = 262144  # Mob can breathe underwater.
    SNEAK = 524288  # Mob can move quietly (room not informed).
    HIDE = 1048576  # Mob is hidden (only visible with sense life).
    FREE = 2097152  # Unused (room for future expansion).
    CHARM = 4194304  # Reserved for internal use. Do not set.


class ZoneFlag(IntFlag):
    """Zone flags (tbaMUD bitvector)."""
    CLOSED = 1  # Zone is closed - players cannot enter.
    NOIMMORT = 2  # Immortals below LVL_GRGOD cannot enter.
    QUEST = 4  # This zone is a quest zone (not implemented).
    GRID = 8  # Zone is 'on the grid', shown in 'areas'.
    NOBUILD = 16  # Building is not allowed in the zone.
    NOASTRAL = 32  # No teleportation magic to or from this zone.
    WORLDMAP = 64  # Whole zone uses the WORLDMAP by default.


class TriggerAttachType(IntEnum):
    """What a DG script trigger attaches to."""
    MOB = 0
    OBJ = 1
    WLD = 2


class MobTriggerType(IntFlag):
    """DG script trigger types for mob triggers (bitvector)."""
    GLOBAL = 1  # Check even if zone empty.
    RANDOM = 2  # Checked randomly.
    COMMAND = 4  # Character types a command.
    SPEECH = 8  # A char says a word/phrase.
    ACT = 16  # An action is done to the mob.
    DEATH = 32  # Character dies.
    GREET = 64  # Something enters room seen.
    GREET_ALL = 128  # Anything enters room.
    ENTRY = 256  # The mob enters a room.
    RECEIVE = 512  # Character is given object.
    FIGHT = 1024  # Each pulse while fighting.
    HITPRCNT = 2048  # Fighting and below some HP percent.
    BRIBE = 4096  # Coins are given to mob.
    LOAD = 8192  # The mob is loaded.
    MEMORY = 16384  # Mob sees a remembered character.
    CAST = 32768  # Mob targeted by spell.
    LEAVE = 65536  # Someone leaves room seen.
    DOOR = 131072  # A door in the room is manipulated.
    TIME = 524288  # Trigger fires at a certain game hour.
    DAMAGE = 1048576  # The mob is damaged (tbaMUD).


class ObjTriggerType(IntFlag):
    """DG script trigger types for object triggers (bitvector)."""
    GLOBAL = 1  # Unused.
    RANDOM = 2  # Checked randomly.
    COMMAND = 4  # Character types a command.
    TIMER = 32  # Object's timer expires.
    GET = 64  # Object is picked up.
    DROP = 128  # Character tries to drop object.
    GIVE = 256  # Character tries to give object.
    WEAR = 512  # Object is worn.
    REMOVE = 2048  # Object is removed.
    LOAD = 8192  # The object is loaded.
    CAST = 32768  # Object targeted by spell.
    LEAVE = 65536  # Someone leaves room seen.
    CONSUME = 262144  # Char tries to eat/drink object.
    TIME = 524288  # Trigger fires at a certain game hour.


class WldTriggerType(IntFlag):
    """DG script trigger types for room triggers (bitvector)."""
    GLOBAL = 1  # Check even if zone empty.
    RANDOM = 2  # Checked randomly.
    COMMAND = 4  # Character types a command.
    SPEECH = 8  # A char says a word/phrase.
    RESET = 32  # Zone has been reset.
    ENTER = 64  # Character enters the room.
    DROP = 128  # Something is dropped in the room.
    CAST = 32768  # A spell is cast in the room.
    LEAVE = 65536  # Character leaves the room.
    DOOR = 131072  # A door in the room is manipulated.
    LOGIN = 262144  # A player logs in to the room (tbaMUD).
    TIME = 524288  # Trigger fires at a certain game hour.


class QuestType(IntEnum):
    """tbaMUD autoquest types."""
    OBJ_FIND = 0  # Player must retrieve object.
    ROOM_FIND = 1  # Player must reach room.
    MOB_FIND = 2  # Player must find mob.
    MOB_KILL = 3  # Player must kill mob.
    MOB_SAVE = 4  # Player must save mob.
    OBJ_RETURN = 5  # Player gives object to mob.
    ROOM_CLEAR = 6  # Player must clear room of all mobs.


class QuestFlag(IntFlag):
    """tbaMUD autoquest flags (bitvector)."""
    REPEATABLE = 1  # Quest can be repeated.


class MobPosition(IntEnum):
    """Mob position."""
    POSITION_DEAD = 0  # Reserved for internal use. Do not set.
    POSITION_MORTALLYW = 1  # Reserved for internal use. Do not set.
    POSITION_INCAP = 2  # Reserved for internal use. Do not set.
    POSITION_STUNNED = 3  # Reserved for internal use. Do not set.
    POSITION_SLEEPING = 4  # The monster is sleeping.
    POSITION_RESTING = 5  # The monster is resting.
    POSITION_SITTING = 6  # The monster is sitting.
    POSITION_FIGHTING = 7  # Reserved for internal use. Do not set.
    POSITION_STANDING = 8  # The monster is standing.


class MobGender(IntEnum):
    """Mob gender."""
    N = 0  # (it/its)
    M = 1  # (he/his)
    F = 2  # (she/her)


class MobEquipSlot(IntEnum):
    """Mob equipment slots."""
    LIGHT = 0  # Used as light
    RING_R = 1  # Worn on right finger
    RING_L = 2  # Worn on left finger
    NECK_1 = 3  # First object worn around neck
    NECK_2 = 4  # Second object worn around neck
    BODY = 5  # Worn on body
    HEAD = 6  # Worn on head
    LEGS = 7  # Worn on legs
    FEET = 8  # Worn on feet
    HANDS = 9  # Worn on hands
    ARMS = 10  # Worn on arms
    SHIELD = 11  # Worn as shield
    ABOUT_BODY = 12  # Worn about body
    WAIST = 13  # Worn around waist
    WRIST_R = 14  # Worn around right wrist
    WRIST_L = 15  # Worn around left wrist
    WIELD = 16  # Wielded as a weapon
    HOLD = 17  # Held


class ShopFlag(IntFlag):
    """Shop flags (bitvector)."""
    WILL_START_FIGHT = 1  # Players can try to kill shopkeeper.
    WILL_BANK_MONEY = 2  # Shopkeeper will put money over 15000 coins in the bank.


class ShopTradesWith(IntFlag):
    """Shop trades-with restrictions (bitvector)."""
    NOGOOD = 1  # Don't trade with positively-aligned players.
    NOEVIL = 2  # Don't trade with evilly-aligned players.
    NONEUTRAL = 4  # Don't trade with neutrally-aligned players.
    NOMAGIC_USER = 8  # Don't trade with the Mage class.
    NOCLERIC = 16  # Don't trade with the Cleric class.
    NOTHIEF = 32  # Don't trade with the Thief class.
    NOWARRIOR = 64  # Don't trade with the Warrior class.
