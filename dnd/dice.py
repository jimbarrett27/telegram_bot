import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class RollResult:
    roll: int
    modifier: int
    total: int
    dc: int
    success: bool
    skill_name: str

    @property
    def description(self) -> str:
        mod_str = f" + {self.modifier}" if self.modifier > 0 else ""
        total_str = f" = {self.total}" if self.modifier > 0 else ""
        outcome = "Success" if self.success else "Failure"
        return f"🎲 {self.skill_name} check (DC {self.dc}): rolled {self.roll}{mod_str}{total_str} — {outcome}!"


def roll_d20() -> int:
    return random.randint(1, 20)


def resolve_check(dc: int, skill_name: str, modifier: int = 0, roll: Optional[int] = None) -> RollResult:
    """Resolve a skill check against a DC.

    If roll is None, rolls a d20 automatically.
    Pass an explicit roll value for the interactive player-roll flow.
    """
    if roll is None:
        roll = roll_d20()
    total = roll + modifier
    return RollResult(
        roll=roll,
        modifier=modifier,
        total=total,
        dc=dc,
        success=total >= dc,
        skill_name=skill_name,
    )
