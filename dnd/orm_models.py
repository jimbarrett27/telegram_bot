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
    joined_at: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("game_id", "telegram_user_id", name="uq_game_player"),
        Index("idx_players_game_id", "game_id"),
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
        joined_at=orm.joined_at or 0,
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
