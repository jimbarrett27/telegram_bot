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
    BARD = "bard"
    DRUID = "druid"
    BARBARIAN = "barbarian"
    MONK = "monk"


class EventType(Enum):
    NARRATION = "narration"
    PLAYER_ACTION = "player_action"
    RESOLUTION = "resolution"
    SYSTEM = "system"
    DM_CLARIFICATION = "dm_clarification"
    PLAYER_CLARIFICATION = "player_clarification"


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
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10
    is_ai: bool = False
    joined_at: int = 0
    id: Optional[int] = None


@dataclass
class InventoryItem:
    player_id: int
    game_id: int
    item_name: str
    item_type: str = "gear"
    quantity: int = 1
    equipped: bool = False
    properties: Optional[str] = None
    created_at: int = 0
    id: Optional[int] = None


@dataclass
class SpellSlots:
    player_id: int
    level_1: int = 0
    level_2: int = 0
    level_3: int = 0
    level_4: int = 0
    level_5: int = 0
    level_6: int = 0
    level_7: int = 0
    level_8: int = 0
    level_9: int = 0
    max_level_1: int = 0
    max_level_2: int = 0
    max_level_3: int = 0
    max_level_4: int = 0
    max_level_5: int = 0
    max_level_6: int = 0
    max_level_7: int = 0
    max_level_8: int = 0
    max_level_9: int = 0
    id: Optional[int] = None


@dataclass
class Game:
    chat_id: int
    status: GameStatus = GameStatus.RECRUITING
    adventure_text: str = ""
    current_player_id: Optional[int] = None
    turn_number: int = 0
    story_summary: str = ""
    campaign_name: str = ""
    recommended_level: int = 1
    created_at: int = 0
    updated_at: int = 0
    id: Optional[int] = None
    players: List[Player] = field(default_factory=list)


@dataclass
class CampaignSection:
    game_id: int
    section_title: str
    section_content: str
    section_order: int = 0
    created_at: int = 0
    id: Optional[int] = None


@dataclass
class DmNote:
    game_id: int
    content: str
    created_at: int = 0
    id: Optional[int] = None


@dataclass
class Zone:
    game_id: int
    name: str
    description: str = ""
    created_at: int = 0
    id: Optional[int] = None


@dataclass
class ZoneAdjacency:
    zone_a_id: int
    zone_b_id: int
    id: Optional[int] = None


@dataclass
class ZoneEntity:
    zone_id: int
    game_id: int
    name: str
    player_id: Optional[int] = None
    entity_type: str = "npc"
    created_at: int = 0
    id: Optional[int] = None


@dataclass
class GameEvent:
    game_id: int
    turn_number: int
    event_type: EventType
    content: str
    actor_player_id: Optional[int] = None
    created_at: int = 0
    id: Optional[int] = None
