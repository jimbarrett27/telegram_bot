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
    GameStatus,
    CharacterClass,
    EventType,
)
from dnd.orm_models import (
    Base,
    GameORM,
    PlayerORM,
    GameEventORM,
    game_orm_to_dataclass,
    player_orm_to_dataclass,
    event_orm_to_dataclass,
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
            hp=20,
            max_hp=20,
            level=1,
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

        # Delete events
        event_stmt = select(GameEventORM).where(GameEventORM.game_id == game_orm.id)
        for event in session.execute(event_stmt).scalars().all():
            session.delete(event)

        # Delete players
        player_stmt = select(PlayerORM).where(PlayerORM.game_id == game_orm.id)
        for player in session.execute(player_stmt).scalars().all():
            session.delete(player)

        # Delete game
        session.delete(game_orm)
