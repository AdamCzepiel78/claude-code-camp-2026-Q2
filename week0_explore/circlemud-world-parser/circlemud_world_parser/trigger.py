"""
Parser for tbaMUD DG script trigger (.trg) files.

Format (see parse_trigger in tbaMUD's dg_db_scripts.c):

    #<vnum>
    <name>~
    <attach type> <trigger type flags> <numeric arg>
    <argument list>~
    <script commands, one per line>
    ~
"""
from pydantic import BaseModel, Field

from .constants import (MobTriggerType, ObjTriggerType, TriggerAttachType,
                        WldTriggerType)
from .models import Flag
from .utils import FlagEnum, lookup_value_to_dict, parse_flags

TRIGGER_TYPE_LOOKUP: dict[int, FlagEnum] = {
    TriggerAttachType.MOB: MobTriggerType,
    TriggerAttachType.OBJ: ObjTriggerType,
    TriggerAttachType.WLD: WldTriggerType,
}


class Trigger(BaseModel):
    """A tbaMUD DG script trigger definition."""

    id: int = Field(..., description="Virtual number (VNUM)")
    name: str = Field(..., description="Trigger name")
    attach_type: Flag = Field(..., description="What the trigger attaches to (0=mob, 1=obj, 2=room)")
    trigger_types: list[Flag] = Field(default_factory=list, description="Events that fire the trigger")
    numeric_arg: int = Field(..., description="Numeric argument (e.g. firing percentage)")
    arg_list: str | None = Field(None, description="Argument list (e.g. command or speech phrase)")
    commands: list[str] = Field(default_factory=list, description="Script command lines")

    @classmethod
    def from_text(cls, text: str) -> "Trigger":
        """Parse a DG script trigger definition from raw text."""
        # Layout by '~' terminators: name ends at the first, the attach
        # line plus argument list end at the second, commands at the third.
        tildes = [i for i, a in enumerate(text) if a == '~']

        head = text[:tildes[0]].split('\n')
        trigger_id = int(head[0])
        name = '\n'.join(head[1:]).strip('\n')

        middle = text[tildes[0] + 1:tildes[1]].strip('\n').split('\n')
        attach_type_raw, type_flags, numeric_arg = middle[0].split()
        arg_list = '\n'.join(middle[1:]) or None

        attach_type = Flag(**lookup_value_to_dict(int(attach_type_raw), TriggerAttachType))
        type_enum = TRIGGER_TYPE_LOOKUP.get(int(attach_type_raw), MobTriggerType)
        trigger_types = parse_flags(type_flags, type_enum)

        commands_raw = text[tildes[1] + 1:tildes[2]].strip('\n')
        commands = commands_raw.split('\n') if commands_raw else []

        return cls(
            id=trigger_id,
            name=name,
            attach_type=attach_type,
            trigger_types=trigger_types,
            numeric_arg=int(numeric_arg),
            arg_list=arg_list,
            commands=commands,
        )
