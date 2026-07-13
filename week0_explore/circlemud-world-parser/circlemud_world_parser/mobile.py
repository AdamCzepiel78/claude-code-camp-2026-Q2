import re
from typing import Literal, cast

from pydantic import BaseModel, Field

from .constants import (MobAction, MobAffect, MobGender, MobPosition,
                        TbaMobAffect)
from .models import Flag
from .utils import lookup_value_to_dict, parse_flags_wide

MobType = Literal["S", "E"]


class DiceRoll(BaseModel):
    """A dice roll formula (e.g., 2d6+10)."""

    dice: int = Field(..., description="Number of dice to roll")
    sides: int = Field(..., description="Number of sides per die")
    bonus: int = Field(..., description="Flat bonus added to roll")

    @classmethod
    def from_string(cls, roll_string: str) -> "DiceRoll":
        """Parse a dice roll string like '4d6+20' or '2d6-5' into a DiceRoll."""
        match = re.match(r"(\d+)d(\d+)([+-]\d+)", roll_string)
        if not match:
            raise ValueError(f"Invalid dice roll string: {roll_string}")
        dice, sides, bonus = match.groups()
        return cls(dice=int(dice), sides=int(sides), bonus=int(bonus))


class Position(BaseModel):
    """Position states for a mobile."""

    load: Flag = Field(..., description="Position when loaded")
    default: Flag = Field(..., description="Default position")


class Mobile(BaseModel):
    """A CircleMUD mobile (NPC) definition."""

    id: int = Field(..., description="Virtual number (VNUM)")
    aliases: list[str] = Field(..., description="Keywords for targeting")
    short_desc: str = Field(..., description="Name shown in actions")
    long_desc: str = Field(..., description="Description in room")
    detail_desc: str = Field(..., description="Description when examined")
    mob_type: MobType = Field(..., description="Mobile type (S=simple, E=extended)")
    alignment: int = Field(..., description="Alignment (-1000 to 1000)")
    flags: list[Flag] = Field(default_factory=list, description="Action flags")
    affects: list[Flag] = Field(default_factory=list, description="Affect flags")
    level: int = Field(..., description="Mobile level")
    thac0: int = Field(..., description="To-hit armor class 0")
    armor_class: int = Field(..., description="Armor class")
    max_hit_points: DiceRoll = Field(..., description="HP dice formula")
    bare_hand_damage: DiceRoll = Field(..., description="Barehanded damage dice")
    gold: int = Field(..., description="Gold carried")
    xp: int = Field(..., description="Experience points awarded")
    position: Position = Field(..., description="Position states")
    gender: Flag = Field(..., description="Gender (N/M/F)")
    extra_spec: dict[str, int] = Field(default_factory=dict, description="Extended specs for E-type mobs")
    triggers: list[int] = Field(default_factory=list, description="Attached DG script trigger VNUMs (tbaMUD)")

    @classmethod
    def from_text(cls, text: str) -> "Mobile":
        """Parse a CircleMUD mobile definition from raw text."""
        fields = [line.rstrip() for line in text.strip().split('\n')]

        mob_id = int(fields[0])
        aliases = fields[1].rstrip('~').split()
        short_desc = fields[2].rstrip('~')
        long_desc = text.split('~')[2].strip('\n')
        detail_desc = text.split('~')[3].strip('\n')

        tildes = [i for i, a in enumerate(text) if a == '~']
        start_bottom_matter = tildes[3] + 1
        bottom_fields = text[start_bottom_matter:].strip('\n').split('\n')

        # Stock CircleMUD: "<action> <affect> <align> <S|E>". tbaMUD 128-bit:
        # "<action x4> <affect x4> <align> <S|E>". tbaMUD also renumbered the
        # affect bits (DONTUSE inserted at bit 0), hence the separate enum.
        vector_tokens = bottom_fields[0].split()
        alignment, mob_type = vector_tokens[-2], vector_tokens[-1]
        flag_fields = vector_tokens[:-2]
        half = len(flag_fields) // 2
        affect_enum = MobAffect if half == 1 else TbaMobAffect

        flags = parse_flags_wide(flag_fields[:half], MobAction)
        affects = parse_flags_wide(flag_fields[half:], affect_enum)

        level, thac0, ac, max_hp, bare_hand_dmg = bottom_fields[1].split()
        gold, xp = bottom_fields[2].split()
        load_position, default_position, gender = bottom_fields[3].split()

        load_dict = lookup_value_to_dict(int(load_position), MobPosition)
        default_dict = lookup_value_to_dict(int(default_position), MobPosition)
        position = Position(load=Flag(**load_dict), default=Flag(**default_dict))

        gender_dict = lookup_value_to_dict(int(gender), MobGender)

        # After the numeric lines: optional "Key: value" especs for E-type
        # mobs (terminated by a lone 'E') and optional "T <vnum>" trigger
        # attach lines (tbaMUD).
        extra_spec = {}
        triggers = []
        for line in bottom_fields[4:]:
            line = line.strip()
            if not line or line == 'E':
                continue
            if line.startswith('T '):
                triggers.append(int(line.split()[1]))
            else:
                key, value = line.split(':', 1)
                extra_spec[key.strip()] = int(value.strip())

        return cls(
            id=mob_id,
            aliases=aliases,
            short_desc=short_desc,
            long_desc=long_desc,
            detail_desc=detail_desc,
            mob_type=cast(MobType, mob_type),
            alignment=int(alignment),
            flags=flags,
            affects=affects,
            level=int(level),
            thac0=int(thac0),
            armor_class=int(ac),
            max_hit_points=DiceRoll.from_string(max_hp),
            bare_hand_damage=DiceRoll.from_string(bare_hand_dmg),
            gold=int(gold),
            xp=int(xp),
            position=position,
            gender=Flag(**gender_dict),
            extra_spec=extra_spec,
            triggers=triggers,
        )
