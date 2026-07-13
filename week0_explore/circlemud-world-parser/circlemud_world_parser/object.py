import re

from pydantic import BaseModel, Field

from .constants import (ObjectAffectLocation, ObjectExtraEffect, ObjectType,
                        ObjectWear, TbaMobAffect)
from .models import ExtraDescription, Flag
from .utils import _lookup_enum, lookup_value_to_dict, parse_flags_wide


class Affect(BaseModel):
    """An affect that modifies a character attribute."""

    location: int = Field(..., description="Affect location code")
    note: str | None = Field(None, description="Human-readable location name")
    value: int = Field(..., description="Modifier value")

    @classmethod
    def from_fields(cls, extra_fields: list[str]) -> list["Affect"]:
        """Parse affects from the 'A' blocks in object data."""
        results = []
        for i, field in enumerate(extra_fields):
            if field == 'A':
                loc, value = (int(v) for v in extra_fields[i + 1].split())
                note = _lookup_enum(loc, ObjectAffectLocation)
                results.append(cls(location=loc, note=note, value=value))
        return results


def parse_extra_descriptions_from_fields(extra_fields: list[str]) -> list[ExtraDescription]:
    """Parse extra descriptions from the 'E' blocks in object data."""
    results = []
    i = 0
    while i < len(extra_fields):
        if extra_fields[i] == 'E':
            i += 1
            keywords = extra_fields[i].rstrip('~').split()
            i += 1
            desc_lines = []
            while i < len(extra_fields) and extra_fields[i] not in ('~', '$'):
                desc_lines.append(extra_fields[i])
                i += 1
            results.append(ExtraDescription(keywords=keywords, desc='\n'.join(desc_lines)))
        i += 1
    return results


class Object(BaseModel):
    """A CircleMUD object definition."""

    id: int = Field(..., description="Virtual number (VNUM)")
    aliases: list[str] = Field(..., description="Keywords for targeting the object")
    short_desc: str = Field(..., description="Name shown in inventory and actions")
    long_desc: str = Field(..., description="Description when object is on the ground")
    action_desc: str | None = Field(None, description="Description when used")
    type: Flag = Field(..., description="Object type (weapon, armor, etc.)")
    effects: list[Flag] = Field(default_factory=list, description="Extra effects (glow, hum, etc.)")
    wear: list[Flag] = Field(default_factory=list, description="Wear positions")
    perm_affects: list[Flag] = Field(default_factory=list, description="Permanent affects when worn (tbaMUD)")
    values: list[int] = Field(..., description="Type-specific values")
    weight: int = Field(..., description="Object weight")
    cost: int = Field(..., description="Value in gold")
    rent: int = Field(..., description="Daily rent cost")
    level: int | None = Field(None, description="Minimum level to use (tbaMUD)")
    timer: int | None = Field(None, description="Object timer (tbaMUD)")
    affects: list[Affect] = Field(default_factory=list, description="Stat modifiers when worn")
    extra_descs: list[ExtraDescription] = Field(default_factory=list, description="Extra descriptions")
    triggers: list[int] = Field(default_factory=list, description="Attached DG script trigger VNUMs (tbaMUD)")

    @classmethod
    def from_text(cls, text: str) -> "Object":
        """Parse a CircleMUD object definition from raw text."""
        # The four leading text fields are '~'-terminated and may span
        # multiple lines, so slice on tilde positions rather than lines.
        tildes = [i for i, a in enumerate(text) if a == '~']
        head = text[:tildes[0]].split('\n')

        obj_id = int(head[0])
        aliases = head[1].split()
        short_desc = text[tildes[0] + 1:tildes[1]].strip('\n')
        long_desc = text[tildes[1] + 1:tildes[2]].strip('\n')
        action_desc = text[tildes[2] + 1:tildes[3]].strip('\n') or None

        fields = [line.rstrip() for line in text[tildes[3] + 1:].strip('\n').split('\n')]

        # Stock CircleMUD: "<type> <effects> <wear>". tbaMUD 128-bit:
        # "<type> <effects x4> <wear x4> <perm affects x4>".
        flag_tokens = fields[0].split()
        type_flag, flag_fields = flag_tokens[0], flag_tokens[1:]
        if len(flag_fields) >= 12:
            effect_fields, wear_fields, perm_fields = (
                flag_fields[0:4], flag_fields[4:8], flag_fields[8:12])
        else:
            effect_fields, wear_fields, perm_fields = (
                flag_fields[:1], flag_fields[1:2], [])

        # type flag is always an int
        type_dict = lookup_value_to_dict(int(type_flag), ObjectType)
        obj_type = Flag(**type_dict)

        # parse the bitvectors
        effects = parse_flags_wide(effect_fields, ObjectExtraEffect)
        wear = parse_flags_wide(wear_fields, ObjectWear)
        perm_affects = parse_flags_wide(perm_fields, TbaMobAffect)

        values = [int(v) for v in fields[1].split()]

        # Stock CircleMUD: "<weight> <cost> <rent>". tbaMUD appends
        # "<level>" and (in newer versions) "<timer>".
        weight_tokens = [int(v) for v in fields[2].split()]
        weight, cost, rent = weight_tokens[:3]
        level = weight_tokens[3] if len(weight_tokens) > 3 else None
        timer = weight_tokens[4] if len(weight_tokens) > 4 else None

        affects = []
        extra_descs = []
        triggers = []
        if len(fields) > 3:
            extra_fields = fields[3:]
            affects = Affect.from_fields(extra_fields)
            extra_descs = parse_extra_descriptions_from_fields(extra_fields)
            triggers = [int(f.split()[1]) for f in extra_fields
                        if re.fullmatch(r'T +\d+', f.strip())]

        return cls(
            id=obj_id,
            aliases=aliases,
            short_desc=short_desc,
            long_desc=long_desc,
            action_desc=action_desc,
            type=obj_type,
            effects=effects,
            wear=wear,
            perm_affects=perm_affects,
            values=values,
            weight=weight,
            cost=cost,
            rent=rent,
            level=level,
            timer=timer,
            affects=affects,
            extra_descs=extra_descs,
            triggers=triggers,
        )
