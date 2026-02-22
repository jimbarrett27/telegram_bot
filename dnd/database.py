"""
Database operations for the D&D game system.

Uses SQLAlchemy ORM for database access. The public API uses the dataclass
models from models.py, with conversion to/from ORM models handled internally.
"""

import time
from typing import List, Optional

from sqlalchemy import select

from dnd.db_engine import get_engine, get_session
from dnd.models import (
    Game,
    Player,
    GameEvent,
    InventoryItem,
    SpellSlots,
    CampaignSection,
    GameStatus,
    CharacterClass,
    EventType,
)
from dnd.orm_models import (
    Base,
    GameORM,
    PlayerORM,
    GameEventORM,
    InventoryItemORM,
    SpellSlotsORM,
    CampaignSectionORM,
    game_orm_to_dataclass,
    player_orm_to_dataclass,
    event_orm_to_dataclass,
    inventory_orm_to_dataclass,
    spell_slots_orm_to_dataclass,
    campaign_section_orm_to_dataclass,
)


def init_db():
    """Initialize the database schema."""
    engine = get_engine()
    Base.metadata.create_all(engine)


def create_game(chat_id: int) -> Game:
    """Create a new game for a chat. Returns the created Game."""
    now = int(time.time())
    with get_session() as session:
        orm = GameORM(
            chat_id=chat_id,
            status=GameStatus.RECRUITING.value,
            adventure_text="",
            turn_number=0,
            created_at=now,
            updated_at=now,
        )
        session.add(orm)
        session.flush()
        return game_orm_to_dataclass(orm)


def get_game_by_id(game_id: int) -> Optional[Game]:
    """Get a game by its ID, including its players."""
    with get_session() as session:
        game_orm = session.get(GameORM, game_id)
        if game_orm is None:
            return None

        player_stmt = select(PlayerORM).where(PlayerORM.game_id == game_orm.id)
        player_orms = session.execute(player_stmt).scalars().all()
        players = [player_orm_to_dataclass(p) for p in player_orms]

        return game_orm_to_dataclass(game_orm, players)


def get_game_by_chat(chat_id: int) -> Optional[Game]:
    """Get a game by chat ID, including its players."""
    with get_session() as session:
        stmt = select(GameORM).where(GameORM.chat_id == chat_id)
        game_orm = session.execute(stmt).scalar_one_or_none()
        if game_orm is None:
            return None

        player_stmt = select(PlayerORM).where(PlayerORM.game_id == game_orm.id)
        player_orms = session.execute(player_stmt).scalars().all()
        players = [player_orm_to_dataclass(p) for p in player_orms]

        return game_orm_to_dataclass(game_orm, players)


def add_player(
    game_id: int,
    telegram_user_id: int,
    telegram_username: str,
    character_name: str,
    character_class: CharacterClass,
    hp: int = 20,
    max_hp: int = 20,
    strength: int = 10,
    dexterity: int = 10,
    constitution: int = 10,
    intelligence: int = 10,
    wisdom: int = 10,
    charisma: int = 10,
) -> Player:
    """Add a player to a game. Returns the created Player."""
    now = int(time.time())
    with get_session() as session:
        orm = PlayerORM(
            game_id=game_id,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            character_name=character_name,
            character_class=character_class.value,
            hp=hp,
            max_hp=max_hp,
            level=1,
            strength=strength,
            dexterity=dexterity,
            constitution=constitution,
            intelligence=intelligence,
            wisdom=wisdom,
            charisma=charisma,
            joined_at=now,
        )
        session.add(orm)
        session.flush()
        return player_orm_to_dataclass(orm)


def get_player_by_user(game_id: int, telegram_user_id: int) -> Optional[Player]:
    """Get a player by game ID and Telegram user ID."""
    with get_session() as session:
        stmt = select(PlayerORM).where(
            PlayerORM.game_id == game_id,
            PlayerORM.telegram_user_id == telegram_user_id,
        )
        orm = session.execute(stmt).scalar_one_or_none()
        if orm is None:
            return None
        return player_orm_to_dataclass(orm)


def get_player_by_id(player_id: int) -> Optional[Player]:
    """Get a player by ID."""
    with get_session() as session:
        orm = session.get(PlayerORM, player_id)
        if orm is None:
            return None
        return player_orm_to_dataclass(orm)


def update_player_hp(player_id: int, hp: int):
    """Update a player's HP."""
    with get_session() as session:
        orm = session.get(PlayerORM, player_id)
        if orm is not None:
            orm.hp = max(0, hp)


def update_game_status(game_id: int, status: GameStatus):
    """Update a game's status."""
    now = int(time.time())
    with get_session() as session:
        orm = session.get(GameORM, game_id)
        if orm is not None:
            orm.status = status.value
            orm.updated_at = now


def update_game_adventure(game_id: int, adventure_text: str):
    """Set the adventure text for a game."""
    now = int(time.time())
    with get_session() as session:
        orm = session.get(GameORM, game_id)
        if orm is not None:
            orm.adventure_text = adventure_text
            orm.updated_at = now


def update_game_current_player(game_id: int, player_id: Optional[int], turn_number: int):
    """Update the current player and turn number."""
    now = int(time.time())
    with get_session() as session:
        orm = session.get(GameORM, game_id)
        if orm is not None:
            orm.current_player_id = player_id
            orm.turn_number = turn_number
            orm.updated_at = now


def add_event(
    game_id: int,
    turn_number: int,
    event_type: EventType,
    content: str,
    actor_player_id: Optional[int] = None,
) -> GameEvent:
    """Add a game event. Returns the created GameEvent."""
    now = int(time.time())
    with get_session() as session:
        orm = GameEventORM(
            game_id=game_id,
            turn_number=turn_number,
            event_type=event_type.value,
            actor_player_id=actor_player_id,
            content=content,
            created_at=now,
        )
        session.add(orm)
        session.flush()
        return event_orm_to_dataclass(orm)


def get_recent_events(game_id: int, limit: int = 30) -> List[GameEvent]:
    """Get the most recent events for a game."""
    with get_session() as session:
        stmt = (
            select(GameEventORM)
            .where(GameEventORM.game_id == game_id)
            .order_by(GameEventORM.id.desc())
            .limit(limit)
        )
        orms = session.execute(stmt).scalars().all()
        events = [event_orm_to_dataclass(orm) for orm in orms]
        events.reverse()  # Return in chronological order
        return events


def delete_game(chat_id: int):
    """Delete a game and all related data for a chat."""
    with get_session() as session:
        stmt = select(GameORM).where(GameORM.chat_id == chat_id)
        game_orm = session.execute(stmt).scalar_one_or_none()
        if game_orm is None:
            return

        # Delete campaign sections
        cs_stmt = select(CampaignSectionORM).where(CampaignSectionORM.game_id == game_orm.id)
        for cs in session.execute(cs_stmt).scalars().all():
            session.delete(cs)

        # Delete inventory items
        inv_stmt = select(InventoryItemORM).where(InventoryItemORM.game_id == game_orm.id)
        for item in session.execute(inv_stmt).scalars().all():
            session.delete(item)

        # Delete spell slots (via players)
        player_stmt = select(PlayerORM).where(PlayerORM.game_id == game_orm.id)
        player_orms = session.execute(player_stmt).scalars().all()
        for player in player_orms:
            ss_stmt = select(SpellSlotsORM).where(SpellSlotsORM.player_id == player.id)
            for ss in session.execute(ss_stmt).scalars().all():
                session.delete(ss)

        # Delete events
        event_stmt = select(GameEventORM).where(GameEventORM.game_id == game_orm.id)
        for event in session.execute(event_stmt).scalars().all():
            session.delete(event)

        # Delete players
        for player in player_orms:
            session.delete(player)

        # Delete game
        session.delete(game_orm)


# --- Inventory operations ---


def add_inventory_item(
    player_id: int,
    game_id: int,
    item_name: str,
    item_type: str = "gear",
    quantity: int = 1,
    equipped: bool = False,
    properties: Optional[str] = None,
) -> InventoryItem:
    """Add an item to a player's inventory."""
    now = int(time.time())
    with get_session() as session:
        orm = InventoryItemORM(
            player_id=player_id,
            game_id=game_id,
            item_name=item_name,
            item_type=item_type,
            quantity=quantity,
            equipped=int(equipped),
            properties=properties,
            created_at=now,
        )
        session.add(orm)
        session.flush()
        return inventory_orm_to_dataclass(orm)


def get_player_inventory(player_id: int) -> List[InventoryItem]:
    """Get all inventory items for a player."""
    with get_session() as session:
        stmt = select(InventoryItemORM).where(InventoryItemORM.player_id == player_id)
        orms = session.execute(stmt).scalars().all()
        return [inventory_orm_to_dataclass(orm) for orm in orms]


def update_inventory_item_quantity(item_id: int, quantity: int):
    """Update the quantity of an inventory item. Deletes if quantity <= 0."""
    with get_session() as session:
        orm = session.get(InventoryItemORM, item_id)
        if orm is None:
            return
        if quantity <= 0:
            session.delete(orm)
        else:
            orm.quantity = quantity


def update_inventory_item_equipped(item_id: int, equipped: bool):
    """Set an inventory item's equipped state."""
    with get_session() as session:
        orm = session.get(InventoryItemORM, item_id)
        if orm is not None:
            orm.equipped = int(equipped)


def remove_inventory_item_by_name(player_id: int, item_name: str, quantity: int = 1) -> bool:
    """Remove quantity of an item from a player's inventory by name.

    Returns True if the item was found and removed/decremented, False otherwise.
    """
    with get_session() as session:
        stmt = select(InventoryItemORM).where(
            InventoryItemORM.player_id == player_id,
            InventoryItemORM.item_name == item_name,
        )
        orm = session.execute(stmt).scalar_one_or_none()
        if orm is None:
            return False
        new_qty = orm.quantity - quantity
        if new_qty <= 0:
            session.delete(orm)
        else:
            orm.quantity = new_qty
        return True


# --- Spell slot operations ---


def create_spell_slots(player_id: int, **slot_values) -> SpellSlots:
    """Create spell slots for a player. Pass level_N and max_level_N kwargs."""
    with get_session() as session:
        orm = SpellSlotsORM(player_id=player_id, **slot_values)
        session.add(orm)
        session.flush()
        return spell_slots_orm_to_dataclass(orm)


def get_spell_slots(player_id: int) -> Optional[SpellSlots]:
    """Get spell slots for a player."""
    with get_session() as session:
        stmt = select(SpellSlotsORM).where(SpellSlotsORM.player_id == player_id)
        orm = session.execute(stmt).scalar_one_or_none()
        if orm is None:
            return None
        return spell_slots_orm_to_dataclass(orm)


def use_spell_slot(player_id: int, level: int) -> bool:
    """Consume one spell slot of the given level. Returns True if successful."""
    if level < 1 or level > 9:
        return False
    col_name = f"level_{level}"
    with get_session() as session:
        stmt = select(SpellSlotsORM).where(SpellSlotsORM.player_id == player_id)
        orm = session.execute(stmt).scalar_one_or_none()
        if orm is None:
            return False
        current = getattr(orm, col_name)
        if current <= 0:
            return False
        setattr(orm, col_name, current - 1)
        return True


def restore_spell_slots(player_id: int):
    """Restore all spell slots to max (long rest)."""
    with get_session() as session:
        stmt = select(SpellSlotsORM).where(SpellSlotsORM.player_id == player_id)
        orm = session.execute(stmt).scalar_one_or_none()
        if orm is None:
            return
        for lvl in range(1, 10):
            setattr(orm, f"level_{lvl}", getattr(orm, f"max_level_{lvl}"))


# --- Player attribute operations ---


def get_player_attributes(player_id: int) -> Optional[dict]:
    """Get a player's ability scores as a dict."""
    with get_session() as session:
        orm = session.get(PlayerORM, player_id)
        if orm is None:
            return None
        return {
            "strength": orm.strength,
            "dexterity": orm.dexterity,
            "constitution": orm.constitution,
            "intelligence": orm.intelligence,
            "wisdom": orm.wisdom,
            "charisma": orm.charisma,
        }


def update_player_attributes(player_id: int, **attrs):
    """Update a player's ability scores. Pass attribute_name=value kwargs."""
    valid_attrs = {"strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"}
    with get_session() as session:
        orm = session.get(PlayerORM, player_id)
        if orm is None:
            return
        for attr, value in attrs.items():
            if attr in valid_attrs:
                setattr(orm, attr, value)


# --- Campaign section operations ---


def store_campaign_sections(game_id: int, sections: list[dict]) -> list[CampaignSection]:
    """Store parsed campaign sections for a game.

    Args:
        game_id: The game ID.
        sections: List of {"title": str, "content": str} dicts.

    Returns:
        List of created CampaignSection dataclasses.
    """
    now = int(time.time())
    results = []
    with get_session() as session:
        for i, section in enumerate(sections):
            orm = CampaignSectionORM(
                game_id=game_id,
                section_title=section["title"],
                section_content=section["content"],
                section_order=i,
                created_at=now,
            )
            session.add(orm)
            session.flush()
            results.append(campaign_section_orm_to_dataclass(orm))
    return results


def get_campaign_sections(game_id: int) -> List[CampaignSection]:
    """Get all campaign sections for a game, ordered by section_order."""
    with get_session() as session:
        stmt = (
            select(CampaignSectionORM)
            .where(CampaignSectionORM.game_id == game_id)
            .order_by(CampaignSectionORM.section_order)
        )
        orms = session.execute(stmt).scalars().all()
        return [campaign_section_orm_to_dataclass(orm) for orm in orms]


def search_campaign_sections(game_id: int, query: str) -> List[CampaignSection]:
    """Search campaign sections by keyword in title or content.

    Returns matching sections ordered by section_order.
    """
    query_lower = query.lower()
    with get_session() as session:
        stmt = (
            select(CampaignSectionORM)
            .where(CampaignSectionORM.game_id == game_id)
            .order_by(CampaignSectionORM.section_order)
        )
        orms = session.execute(stmt).scalars().all()
        matches = []
        for orm in orms:
            if (query_lower in orm.section_title.lower()
                    or query_lower in orm.section_content.lower()):
                matches.append(campaign_section_orm_to_dataclass(orm))
        return matches
