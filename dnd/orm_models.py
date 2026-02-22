"""
SQLAlchemy ORM models for the D&D game system.

These models are internal to the database layer. The public interface
uses the dataclass models from models.py.
"""

import time
from typing import Optional

from sqlalchemy import Integer, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from dnd.models import (
    Game,
    Player,
    GameEvent,
    InventoryItem,
    SpellSlots,
    CampaignSection,
    DmNote,
    GameStatus,
    CharacterClass,
    EventType,
)


class Base(DeclarativeBase):
    pass


class GameORM(Base):
    """SQLAlchemy model for games table."""

    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="recruiting")
    adventure_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    current_player_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    story_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False)


class PlayerORM(Base):
    """SQLAlchemy model for players table."""

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    telegram_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    telegram_username: Mapped[str] = mapped_column(Text, nullable=False)
    character_name: Mapped[str] = mapped_column(Text, nullable=False)
    character_class: Mapped[str] = mapped_column(Text, nullable=False)
    hp: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    max_hp: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    strength: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    dexterity: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    constitution: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    intelligence: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    wisdom: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    charisma: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    is_ai: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    joined_at: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("game_id", "telegram_user_id", name="uq_game_player"),
        Index("idx_players_game_id", "game_id"),
    )


class InventoryItemORM(Base):
    """SQLAlchemy model for inventory_items table."""

    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    item_name: Mapped[str] = mapped_column(Text, nullable=False)
    item_type: Mapped[str] = mapped_column(Text, nullable=False, default="gear")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    equipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    properties: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("idx_inventory_player_id", "player_id"),
        Index("idx_inventory_game_id", "game_id"),
    )


class SpellSlotsORM(Base):
    """SQLAlchemy model for spell_slots table."""

    __tablename__ = "spell_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    level_1: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level_2: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level_3: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level_4: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level_5: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level_6: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level_7: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level_8: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level_9: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_level_1: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_level_2: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_level_3: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_level_4: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_level_5: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_level_6: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_level_7: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_level_8: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_level_9: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("player_id", name="uq_spell_slots_player"),
    )


class GameEventORM(Base):
    """SQLAlchemy model for game_events table."""

    __tablename__ = "game_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_player_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("idx_game_events_game_id", "game_id"),
    )


class CampaignSectionORM(Base):
    """SQLAlchemy model for campaign_sections table."""

    __tablename__ = "campaign_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    section_title: Mapped[str] = mapped_column(Text, nullable=False)
    section_content: Mapped[str] = mapped_column(Text, nullable=False)
    section_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("idx_campaign_sections_game_id", "game_id"),
    )


class DmNoteORM(Base):
    """SQLAlchemy model for dm_notes table."""

    __tablename__ = "dm_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("idx_dm_notes_game_id", "game_id"),
    )


# Conversion functions


def game_orm_to_dataclass(orm: GameORM, players: list[Player] | None = None) -> Game:
    """Convert a GameORM instance to a Game dataclass."""
    return Game(
        id=orm.id,
        chat_id=orm.chat_id,
        status=GameStatus(orm.status),
        adventure_text=orm.adventure_text or "",
        current_player_id=orm.current_player_id,
        turn_number=orm.turn_number or 0,
        story_summary=orm.story_summary or "",
        created_at=orm.created_at or 0,
        updated_at=orm.updated_at or 0,
        players=players or [],
    )


def player_orm_to_dataclass(orm: PlayerORM) -> Player:
    """Convert a PlayerORM instance to a Player dataclass."""
    return Player(
        id=orm.id,
        game_id=orm.game_id,
        telegram_user_id=orm.telegram_user_id,
        telegram_username=orm.telegram_username,
        character_name=orm.character_name,
        character_class=CharacterClass(orm.character_class),
        hp=orm.hp,
        max_hp=orm.max_hp,
        level=orm.level,
        strength=orm.strength,
        dexterity=orm.dexterity,
        constitution=orm.constitution,
        intelligence=orm.intelligence,
        wisdom=orm.wisdom,
        charisma=orm.charisma,
        is_ai=bool(orm.is_ai),
        joined_at=orm.joined_at or 0,
    )


def inventory_orm_to_dataclass(orm: InventoryItemORM) -> InventoryItem:
    """Convert an InventoryItemORM instance to an InventoryItem dataclass."""
    return InventoryItem(
        id=orm.id,
        player_id=orm.player_id,
        game_id=orm.game_id,
        item_name=orm.item_name,
        item_type=orm.item_type,
        quantity=orm.quantity,
        equipped=bool(orm.equipped),
        properties=orm.properties,
        created_at=orm.created_at or 0,
    )


def spell_slots_orm_to_dataclass(orm: SpellSlotsORM) -> SpellSlots:
    """Convert a SpellSlotsORM instance to a SpellSlots dataclass."""
    return SpellSlots(
        id=orm.id,
        player_id=orm.player_id,
        level_1=orm.level_1,
        level_2=orm.level_2,
        level_3=orm.level_3,
        level_4=orm.level_4,
        level_5=orm.level_5,
        level_6=orm.level_6,
        level_7=orm.level_7,
        level_8=orm.level_8,
        level_9=orm.level_9,
        max_level_1=orm.max_level_1,
        max_level_2=orm.max_level_2,
        max_level_3=orm.max_level_3,
        max_level_4=orm.max_level_4,
        max_level_5=orm.max_level_5,
        max_level_6=orm.max_level_6,
        max_level_7=orm.max_level_7,
        max_level_8=orm.max_level_8,
        max_level_9=orm.max_level_9,
    )


def event_orm_to_dataclass(orm: GameEventORM) -> GameEvent:
    """Convert a GameEventORM instance to a GameEvent dataclass."""
    return GameEvent(
        id=orm.id,
        game_id=orm.game_id,
        turn_number=orm.turn_number,
        event_type=EventType(orm.event_type),
        actor_player_id=orm.actor_player_id,
        content=orm.content,
        created_at=orm.created_at or 0,
    )


def dm_note_orm_to_dataclass(orm: DmNoteORM) -> DmNote:
    """Convert a DmNoteORM instance to a DmNote dataclass."""
    return DmNote(
        id=orm.id,
        game_id=orm.game_id,
        content=orm.content,
        created_at=orm.created_at or 0,
    )


def campaign_section_orm_to_dataclass(orm: CampaignSectionORM) -> CampaignSection:
    """Convert a CampaignSectionORM instance to a CampaignSection dataclass."""
    return CampaignSection(
        id=orm.id,
        game_id=orm.game_id,
        section_title=orm.section_title,
        section_content=orm.section_content,
        section_order=orm.section_order,
        created_at=orm.created_at or 0,
    )
