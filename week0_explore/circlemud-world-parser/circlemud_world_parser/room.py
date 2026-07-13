import re

from pydantic import BaseModel, Field

from .constants import RoomDoorFlag, RoomFlag, RoomSectorType
from .models import ExtraDescription, Flag
from .utils import (_lookup_enum, lookup_value_to_dict, parse_flags_wide)

EXIT_RE = r"""D(\d+)
(.*?)~
(.*?)~
(.*?)
"""
EXIT_PATTERN = re.compile(EXIT_RE, re.DOTALL | re.MULTILINE)

EXTRA_DESC_RE = r"""E
(.*?)~
(.*?)
~"""
EXTRA_DESC_PATTERN = re.compile(EXTRA_DESC_RE, re.DOTALL)

TRIGGER_PATTERN = re.compile(r'^T +(\d+)\s*$', re.MULTILINE)


class Exit(BaseModel):
    """An exit leading to another room."""

    dir: int = Field(..., description="Direction code (0=N, 1=E, 2=S, 3=W, 4=U, 5=D)")
    desc: str = Field(..., description="Description when looking in this direction")
    keywords: list[str] = Field(default_factory=list, description="Keywords for the door")
    key_number: int = Field(..., description="VNUM of key object, or -1 if none")
    room_linked: int = Field(..., description="VNUM of destination room")
    door_flag: Flag = Field(..., description="Door type (none, door, pickproof)")

    @classmethod
    def from_text(cls, text: str) -> list["Exit"]:
        """Parse exits from room bottom matter text."""
        exits = []
        matches = EXIT_PATTERN.findall(text)
        for match in matches:
            direction, desc, keys, other = match
            desc = desc.rstrip('\n')
            flag, key_num, to = other.strip().split()

            door_flag = Flag(value=int(flag), note=_lookup_enum(int(flag), RoomDoorFlag))
            exits.append(cls(
                dir=int(direction),
                desc=desc,
                keywords=keys.split(),
                key_number=int(key_num),
                room_linked=int(to),
                door_flag=door_flag,
            ))
        return exits


class Room(BaseModel):
    """A CircleMUD room definition."""

    id: int = Field(..., description="Virtual number (VNUM)")
    name: str = Field(..., description="Room name shown to players")
    desc: str = Field(..., description="Room description")
    zone_number: int = Field(..., description="Zone this room belongs to")
    flags: list[Flag] = Field(default_factory=list, description="Room flags (dark, nomob, etc.)")
    sector_type: Flag = Field(..., description="Terrain type")
    exits: list[Exit] = Field(default_factory=list, description="Exits to other rooms")
    extra_descs: list[ExtraDescription] = Field(default_factory=list, description="Extra descriptions")
    triggers: list[int] = Field(default_factory=list, description="Attached DG script trigger VNUMs (tbaMUD)")

    @staticmethod
    def parse_extra_descriptions_from_text(text: str) -> list[ExtraDescription]:
        """Parse extra descriptions from room bottom matter text."""
        extra_descs = []
        for keywords, desc in EXTRA_DESC_PATTERN.findall(text):
            extra_descs.append(ExtraDescription(keywords=keywords.split(), desc=desc))
        return extra_descs

    @classmethod
    def from_text(cls, text: str) -> "Room":
        """Parse a CircleMUD room definition from raw text."""
        lines = text.split('\n')
        vnum = lines[0]
        # Like the game's fread_string: the first '~' terminates the name
        # and the rest of the line is discarded (some room names contain
        # literal tildes, e.g. "Welcors ~~~ ~~~ furnace~").
        name = lines[1].split('~')[0]

        body = '\n'.join(lines[2:])
        desc, _, rest = body.partition('~')
        rest_lines = rest.split('\n')[1:]  # drop remainder of the '~' line

        # Stock CircleMUD: "<zone> <flags> <sector>". tbaMUD 128-bit:
        # "<zone> <flags1> <flags2> <flags3> <flags4> <sector>".
        header = rest_lines[0].strip().split()
        zone, flag_fields, sector = header[0], header[1:-1], header[-1]

        flags = parse_flags_wide(flag_fields, RoomFlag)

        sector_dict = lookup_value_to_dict(int(sector), RoomSectorType)
        sector_type = Flag(**sector_dict)

        bottom_matter = '\n'.join(rest_lines[1:])
        exits = Exit.from_text(bottom_matter)
        extra_descs = cls.parse_extra_descriptions_from_text(bottom_matter)
        triggers = [int(t) for t in TRIGGER_PATTERN.findall(bottom_matter)]

        return cls(
            id=int(vnum),
            name=name.strip(),
            desc=desc.strip(),
            zone_number=int(zone),
            flags=flags,
            sector_type=sector_type,
            exits=exits,
            extra_descs=extra_descs,
            triggers=triggers,
        )
