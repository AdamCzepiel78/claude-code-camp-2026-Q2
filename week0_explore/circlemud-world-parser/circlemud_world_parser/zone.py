from pydantic import BaseModel, Field

from .constants import MobEquipSlot, TriggerAttachType, ZoneFlag
from .models import Flag
from .utils import _lookup_enum, parse_flags_wide


class ObjectContainer(BaseModel):
    """An object that can contain other objects."""

    id: int = Field(..., description="Object VNUM")
    max: int = Field(..., description="Maximum number to load")
    contents: list["ObjectContainer"] = Field(default_factory=list, description="Contained objects")


class EquippedObject(BaseModel):
    """An object equipped on a mob."""

    id: int = Field(..., description="Object VNUM")
    max: int = Field(..., description="Maximum number to load")
    location: int = Field(..., description="Equipment slot code")
    note: str | None = Field(None, description="Human-readable slot name")
    contents: list[ObjectContainer] = Field(default_factory=list, description="Contained objects")


class InventoryObject(BaseModel):
    """An object in a mob's inventory."""

    id: int = Field(..., description="Object VNUM")
    max: int = Field(..., description="Maximum number to load")
    contents: list[ObjectContainer] = Field(default_factory=list, description="Contained objects")


class ZoneMob(BaseModel):
    """A mob to be loaded in a zone."""

    mob: int = Field(..., description="Mobile VNUM")
    max: int = Field(..., description="Maximum number to load")
    room: int = Field(..., description="Room VNUM to load in")
    inventory: list[InventoryObject] = Field(default_factory=list, description="Inventory items")
    equipped: list[EquippedObject] = Field(default_factory=list, description="Equipped items")


class ZoneObject(BaseModel):
    """An object to be loaded in a zone."""

    id: int = Field(..., description="Object VNUM")
    max: int = Field(..., description="Maximum number to load")
    room: int = Field(..., description="Room VNUM to load in")
    contents: list[ObjectContainer] = Field(default_factory=list, description="Contained objects")


class Door(BaseModel):
    """A door state to set on zone reset."""

    room: int = Field(..., description="Room VNUM")
    exit: int = Field(..., description="Exit direction")
    state: int = Field(..., description="Door state (0=open, 1=closed, 2=locked)")


class RemoveObject(BaseModel):
    """An object to remove from a room on zone reset."""

    room: int = Field(..., description="Room VNUM")
    id: int = Field(..., description="Object VNUM to remove")


class TriggerAttach(BaseModel):
    """A DG script trigger attached on zone reset (tbaMUD 'T' command)."""

    trigger_type: Flag = Field(..., description="What the trigger attaches to (0=mob, 1=obj, 2=room)")
    id: int = Field(..., description="Trigger VNUM")
    room: int | None = Field(None, description="Room VNUM for room-type triggers")


class Zone(BaseModel):
    """A CircleMUD zone definition."""

    id: int = Field(..., description="Zone number")
    name: str = Field(..., description="Zone name")
    builders: str | None = Field(None, description="Builder credits (tbaMUD)")
    bottom_room: int = Field(..., description="First room VNUM in zone")
    top_room: int = Field(..., description="Last room VNUM in zone")
    lifespan: int = Field(..., description="Minutes between zone resets")
    reset_mode: int = Field(..., description="Reset mode (0=never, 1=empty, 2=always)")
    flags: list[Flag] = Field(default_factory=list, description="Zone flags (tbaMUD)")
    min_level: int | None = Field(None, description="Minimum level to enter (tbaMUD, -1=none)")
    max_level: int | None = Field(None, description="Maximum level to enter (tbaMUD, -1=none)")
    mobs: list[ZoneMob] = Field(default_factory=list, description="Mobs to load")
    objects: list[ZoneObject] = Field(default_factory=list, description="Objects to load")
    doors: list[Door] = Field(default_factory=list, description="Doors to set")
    remove_objects: list[RemoveObject] = Field(default_factory=list, description="Objects to remove")
    triggers: list[TriggerAttach] = Field(default_factory=list, description="Triggers attached on reset (tbaMUD)")

    @classmethod
    def from_text(cls, text: str) -> "Zone":
        """Parse a CircleMUD zone definition from raw text."""
        fields = [line.rstrip() for line in text.strip().split('\n')]

        # remove comment lines
        fields = [f for f in fields if not f.startswith('*')]

        zone_id = int(fields[0])

        # tbaMUD zones have a builder-credits line before the name; stock
        # CircleMUD only has the name. Two consecutive '~' lines mean the
        # first is the builders line.
        idx = 1
        builders = None
        if fields[idx + 1].endswith('~'):
            builders = fields[idx].rstrip('~')
            idx += 1
        name = fields[idx].rstrip('~')

        # Stock CircleMUD: "<bot> <top> <lifespan> <reset>". tbaMUD appends
        # "<zone flags x4> <min level> <max level>".
        header = fields[idx + 1].split()
        bottom, top, lifespan, reset_mode = map(int, header[:4])
        flags = []
        min_level = max_level = None
        if len(header) >= 10:
            flags = parse_flags_wide(header[4:8], ZoneFlag)
            min_level, max_level = int(header[8]), int(header[9])

        commands = fields[idx + 2:]
        mobs, objects, doors, remove_objects, triggers = cls._parse_commands(commands)

        return cls(
            id=zone_id,
            name=name,
            builders=builders,
            bottom_room=bottom,
            top_room=top,
            lifespan=lifespan,
            reset_mode=reset_mode,
            flags=flags,
            min_level=min_level,
            max_level=max_level,
            mobs=mobs,
            objects=objects,
            doors=doors,
            remove_objects=remove_objects,
            triggers=triggers,
        )

    @classmethod
    def _get_command_fields(cls, command: str, n_fields: int = 4) -> list[int]:
        """Extract numeric fields from a zone command.

        Splits on whitespace so negative arguments parse correctly and
        trailing builder comments like "(the gateguard key)" are ignored.
        """
        results: list[int] = []
        for token in command.split()[1:]:
            try:
                results.append(int(token))
            except ValueError:
                break
            if len(results) == n_fields:
                break
        return results

    @classmethod
    def _get_contents(cls, commands: list[str], i: int, curr_obj: int) -> list[ObjectContainer]:
        """Recursively get contents of a container."""
        contents = []
        i += 1
        while i < len(commands) and commands[i].startswith('P'):
            _, new_object, max_count, container = cls._get_command_fields(commands[i])
            if container == curr_obj:
                subcontents = cls._get_contents(commands, i, new_object)
                contents.append(ObjectContainer(id=new_object, max=max_count, contents=subcontents))
            i += 1
        return contents

    @classmethod
    def _parse_commands(cls, commands: list[str]) -> tuple[list[ZoneMob], list[ZoneObject], list[Door], list[RemoveObject], list["TriggerAttach"]]:
        """Parse zone commands into structured data."""
        mobs = []
        objects = []
        doors = []
        remove_objects = []
        triggers = []

        for i, curr in enumerate(commands):
            if curr == 'S':
                break

            elif curr.startswith('M'):
                _, mob, max_count, room = cls._get_command_fields(curr)
                mobs.append(ZoneMob(mob=mob, max=max_count, room=room, inventory=[], equipped=[]))

            elif curr.startswith('E'):
                _, obj, max_count, location = cls._get_command_fields(curr)
                note = _lookup_enum(location, MobEquipSlot)
                contents = cls._get_contents(commands, i, obj)
                mobs[-1].equipped.append(EquippedObject(
                    location=location, max=max_count, id=obj, note=note, contents=contents
                ))

            elif curr.startswith('G'):
                _, obj, max_count = cls._get_command_fields(curr, 3)
                contents = cls._get_contents(commands, i, obj)
                mobs[-1].inventory.append(InventoryObject(max=max_count, id=obj, contents=contents))

            elif curr.startswith('O'):
                _, obj, max_count, room = cls._get_command_fields(curr)
                contents = cls._get_contents(commands, i, obj)
                objects.append(ZoneObject(max=max_count, id=obj, room=room, contents=contents))

            elif curr.startswith('D'):
                _, room, exit_dir, state = cls._get_command_fields(curr)
                doors.append(Door(room=room, exit=exit_dir, state=state))

            elif curr.startswith('R'):
                _, room, obj = cls._get_command_fields(curr, 3)
                remove_objects.append(RemoveObject(room=room, id=obj))

            elif curr.startswith('T'):
                # tbaMUD: T <if_flag> <attach type> <trigger vnum> <room for room-type>
                parts = cls._get_command_fields(curr)
                attach_type, trig = parts[1], parts[2]
                is_room_trigger = attach_type == TriggerAttachType.WLD and len(parts) > 3
                note = _lookup_enum(attach_type, TriggerAttachType)
                triggers.append(TriggerAttach(
                    trigger_type=Flag(value=attach_type, note=note),
                    id=trig,
                    room=parts[3] if is_room_trigger else None,
                ))

        return mobs, objects, doors, remove_objects, triggers
