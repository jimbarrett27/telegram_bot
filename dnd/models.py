"""
Data models for the D&D async game system.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List


class GameStatus(Enum):
    RECRUITING = "recruiting"
    ACTIVE = "active"
    FINISHED = "finished"


class CharacterClass(Enum):
    WARRIOR = "warrior"
    MAGE = "mage"
    ROGUE = "rogue"
    CLERIC = "cleric"


class EventType(Enum):
    NARRATION = "narration"
    PLAYER_ACTION = "player_action"
    RESOLUTION = "resolution"
    SYSTEM = "system"


@dataclass
class Player:
    game_id: int
    telegram_user_id: int
    telegram_username: str
    character_name: str
    character_class: CharacterClass
    hp: int = 20
    max_hp: int = 20
    level: int = 1
    joined_at: int = 0
    id: Optional[int] = None


@dataclass
class Game:
    chat_id: int
    status: GameStatus = GameStatus.RECRUITING
    adventure_text: str = ""
    current_player_id: Optional[int] = None
    turn_number: int = 0
    created_at: int = 0
    updated_at: int = 0
    id: Optional[int] = None
    players: List[Player] = field(default_factory=list)


@dataclass
class GameEvent:
    game_id: int
    turn_number: int
    event_type: EventType
    content: str
    actor_player_id: Optional[int] = None
    created_at: int = 0
    id: Optional[int] = None
