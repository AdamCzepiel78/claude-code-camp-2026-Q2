"""
Parser for tbaMUD autoquest (.qst) files.

Format (see parse_quest in tbaMUD's quest.c):

    #<vnum>
    <name>~
    <description>~
    <info shown on quest join>~
    <completion message>~
    <abandon message>~
    <type> <questmaster> <flags> <target> <prev quest> <next quest> <prereq object>
    <points> <penalty> <min level> <max level> <time limit> <return mob> <quantity>
    <gold reward> <exp reward> <object reward>
    S
"""
from pydantic import BaseModel, Field

from .constants import QuestFlag, QuestType
from .models import Flag
from .utils import lookup_value_to_dict, parse_flags


class Quest(BaseModel):
    """A tbaMUD autoquest definition."""

    id: int = Field(..., description="Virtual number (VNUM)")
    name: str = Field(..., description="Quest name")
    desc: str = Field(..., description="Short description shown in quest lists")
    info: str = Field(..., description="Details shown when the quest is joined")
    completion_message: str = Field(..., description="Message shown on completion")
    abandon_message: str = Field(..., description="Message shown when abandoned")
    type: Flag = Field(..., description="Quest type (kill mob, find object, etc.)")
    questmaster: int = Field(..., description="Questmaster mobile VNUM")
    flags: list[Flag] = Field(default_factory=list, description="Quest flags")
    target: int = Field(..., description="Target VNUM (meaning depends on type), -1 if none")
    prev_quest: int = Field(..., description="Prerequisite quest VNUM, -1 if none")
    next_quest: int = Field(..., description="Follow-up quest VNUM, -1 if none")
    prereq_object: int = Field(..., description="Prerequisite object VNUM, -1 if none")
    points: int = Field(..., description="Quest points awarded on completion")
    penalty: int = Field(..., description="Quest point penalty for abandoning/failing")
    min_level: int = Field(..., description="Minimum player level")
    max_level: int = Field(..., description="Maximum player level")
    time_limit: int = Field(..., description="Time limit in ticks, -1 if none")
    return_mob: int = Field(..., description="Mob VNUM to return the object to")
    quantity: int = Field(..., description="Number of targets required")
    gold_reward: int = Field(..., description="Gold awarded on completion")
    exp_reward: int = Field(..., description="Experience awarded on completion")
    obj_reward: int = Field(..., description="Object VNUM awarded, -1 if none")

    @classmethod
    def from_text(cls, text: str) -> "Quest":
        """Parse a tbaMUD autoquest definition from raw text."""
        parts = text.split('~')
        quest_id = int(parts[0].split('\n')[0])
        name = '\n'.join(parts[0].split('\n')[1:]).strip('\n')
        desc = parts[1].strip('\n')
        info = parts[2].strip('\n')
        completion_message = parts[3].strip('\n')
        abandon_message = parts[4].strip('\n')

        numeric_lines = [
            line for line in parts[5].strip('\n').split('\n')
            if line.strip() and line.strip() != 'S'
        ]
        header = numeric_lines[0].split()
        quest_type = Flag(**lookup_value_to_dict(int(header[0]), QuestType))
        questmaster = int(header[1])
        flags = parse_flags(header[2], QuestFlag)
        target, prev_quest, next_quest, prereq_object = (int(v) for v in header[3:7])

        values = [int(v) for v in numeric_lines[1].split()]
        points, penalty, min_level, max_level, time_limit, return_mob, quantity = values

        gold_reward, exp_reward, obj_reward = (int(v) for v in numeric_lines[2].split())

        return cls(
            id=quest_id,
            name=name,
            desc=desc,
            info=info,
            completion_message=completion_message,
            abandon_message=abandon_message,
            type=quest_type,
            questmaster=questmaster,
            flags=flags,
            target=target,
            prev_quest=prev_quest,
            next_quest=next_quest,
            prereq_object=prereq_object,
            points=points,
            penalty=penalty,
            min_level=min_level,
            max_level=max_level,
            time_limit=time_limit,
            return_mob=return_mob,
            quantity=quantity,
            gold_reward=gold_reward,
            exp_reward=exp_reward,
            obj_reward=obj_reward,
        )
