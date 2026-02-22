"""Tests for D&D game database operations."""

import time

import pytest
from sqlalchemy import create_engine, text

from dnd import db_engine
from dnd.models import GameStatus, CharacterClass, EventType
from dnd.orm_models import Base


@pytest.fixture
def temp_db():
    """Create a temporary in-memory database for testing."""
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)
    db_engine.set_engine(test_engine)
    yield test_engine
    db_engine.reset_engine()


class TestInitDb:
    """Tests for database initialization."""

    def test_creates_tables(self, temp_db):
        """Test that init_db creates all required tables."""
        with temp_db.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            tables = {row[0] for row in result.fetchall()}

        assert "games" in tables
        assert "players" in tables
        assert "game_events" in tables

    def test_idempotent(self, temp_db):
        """Test that init_db can be called multiple times safely."""
        from dnd.database import init_db

        init_db()
        init_db()


class TestGameOperations:
    """Tests for game CRUD operations."""

    def test_create_game(self, temp_db):
        """Test creating a game."""
        from dnd.database import create_game

        game = create_game(chat_id=12345)
        assert game is not None
        assert game.id is not None
        assert game.chat_id == 12345
        assert game.status == GameStatus.RECRUITING
        assert game.turn_number == 0

    def test_get_game_by_chat(self, temp_db):
        """Test getting a game by chat ID."""
        from dnd.database import create_game, get_game_by_chat

        create_game(chat_id=12345)
        game = get_game_by_chat(12345)
        assert game is not None
        assert game.chat_id == 12345

    def test_get_game_by_chat_not_found(self, temp_db):
        """Test getting a non-existent game returns None."""
        from dnd.database import get_game_by_chat

        result = get_game_by_chat(99999)
        assert result is None

    def test_update_game_status(self, temp_db):
        """Test updating game status."""
        from dnd.database import create_game, get_game_by_chat, update_game_status

        game = create_game(chat_id=12345)
        update_game_status(game.id, GameStatus.ACTIVE)

        updated = get_game_by_chat(12345)
        assert updated.status == GameStatus.ACTIVE

    def test_update_game_adventure(self, temp_db):
        """Test setting adventure text."""
        from dnd.database import create_game, get_game_by_chat, update_game_adventure

        game = create_game(chat_id=12345)
        update_game_adventure(game.id, "A dark cave awaits...")

        updated = get_game_by_chat(12345)
        assert updated.adventure_text == "A dark cave awaits..."

    def test_update_game_current_player(self, temp_db):
        """Test updating current player and turn."""
        from dnd.database import create_game, get_game_by_chat, update_game_current_player

        game = create_game(chat_id=12345)
        update_game_current_player(game.id, player_id=42, turn_number=3)

        updated = get_game_by_chat(12345)
        assert updated.current_player_id == 42
        assert updated.turn_number == 3

    def test_delete_game(self, temp_db):
        """Test deleting a game and all related data."""
        from dnd.database import (
            create_game, get_game_by_chat, add_player, add_event, delete_game,
        )

        game = create_game(chat_id=12345)
        add_player(game.id, 111, "alice", "Alice", CharacterClass.WARRIOR)
        add_event(game.id, 1, EventType.SYSTEM, "Game started")

        delete_game(12345)
        assert get_game_by_chat(12345) is None


class TestPlayerOperations:
    """Tests for player CRUD operations."""

    def test_add_player(self, temp_db):
        """Test adding a player to a game."""
        from dnd.database import create_game, add_player

        game = create_game(chat_id=12345)
        player = add_player(
            game_id=game.id,
            telegram_user_id=111,
            telegram_username="alice",
            character_name="Alara",
            character_class=CharacterClass.MAGE,
        )

        assert player is not None
        assert player.id is not None
        assert player.character_name == "Alara"
        assert player.character_class == CharacterClass.MAGE
        assert player.hp == 20
        assert player.max_hp == 20

    def test_get_player_by_user(self, temp_db):
        """Test getting a player by game and user ID."""
        from dnd.database import create_game, add_player, get_player_by_user

        game = create_game(chat_id=12345)
        add_player(game.id, 111, "alice", "Alara", CharacterClass.MAGE)

        player = get_player_by_user(game.id, 111)
        assert player is not None
        assert player.character_name == "Alara"

    def test_get_player_by_user_not_found(self, temp_db):
        """Test getting a non-existent player returns None."""
        from dnd.database import create_game, get_player_by_user

        game = create_game(chat_id=12345)
        result = get_player_by_user(game.id, 99999)
        assert result is None

    def test_get_player_by_id(self, temp_db):
        """Test getting a player by ID."""
        from dnd.database import create_game, add_player, get_player_by_id

        game = create_game(chat_id=12345)
        player = add_player(game.id, 111, "alice", "Alara", CharacterClass.ROGUE)

        fetched = get_player_by_id(player.id)
        assert fetched is not None
        assert fetched.character_name == "Alara"
        assert fetched.character_class == CharacterClass.ROGUE

    def test_update_player_hp(self, temp_db):
        """Test updating a player's HP."""
        from dnd.database import create_game, add_player, get_player_by_id, update_player_hp

        game = create_game(chat_id=12345)
        player = add_player(game.id, 111, "alice", "Alara", CharacterClass.WARRIOR)

        update_player_hp(player.id, 15)
        updated = get_player_by_id(player.id)
        assert updated.hp == 15

    def test_update_player_hp_clamps_to_zero(self, temp_db):
        """Test that HP cannot go below zero."""
        from dnd.database import create_game, add_player, get_player_by_id, update_player_hp

        game = create_game(chat_id=12345)
        player = add_player(game.id, 111, "alice", "Alara", CharacterClass.WARRIOR)

        update_player_hp(player.id, -5)
        updated = get_player_by_id(player.id)
        assert updated.hp == 0

    def test_game_includes_players(self, temp_db):
        """Test that getting a game includes its players."""
        from dnd.database import create_game, add_player, get_game_by_chat

        game = create_game(chat_id=12345)
        add_player(game.id, 111, "alice", "Alara", CharacterClass.WARRIOR)
        add_player(game.id, 222, "bob", "Bork", CharacterClass.CLERIC)

        loaded = get_game_by_chat(12345)
        assert len(loaded.players) == 2
        names = {p.character_name for p in loaded.players}
        assert names == {"Alara", "Bork"}

    def test_all_character_classes(self, temp_db):
        """Test that all character classes are stored and retrieved correctly."""
        from dnd.database import create_game, add_player, get_player_by_user

        game = create_game(chat_id=12345)
        for i, cls in enumerate(CharacterClass):
            add_player(game.id, 100 + i, f"user{i}", f"Char{i}", cls)

            player = get_player_by_user(game.id, 100 + i)
            assert player.character_class == cls


class TestEventOperations:
    """Tests for game event operations."""

    def test_add_event(self, temp_db):
        """Test adding a game event."""
        from dnd.database import create_game, add_event

        game = create_game(chat_id=12345)
        event = add_event(
            game_id=game.id,
            turn_number=1,
            event_type=EventType.NARRATION,
            content="The cave entrance looms before you.",
        )

        assert event is not None
        assert event.id is not None
        assert event.event_type == EventType.NARRATION
        assert event.content == "The cave entrance looms before you."

    def test_add_event_with_actor(self, temp_db):
        """Test adding an event with an actor player."""
        from dnd.database import create_game, add_player, add_event

        game = create_game(chat_id=12345)
        player = add_player(game.id, 111, "alice", "Alara", CharacterClass.WARRIOR)
        event = add_event(
            game_id=game.id,
            turn_number=1,
            event_type=EventType.PLAYER_ACTION,
            content="I attack the goblin!",
            actor_player_id=player.id,
        )

        assert event.actor_player_id == player.id
        assert event.event_type == EventType.PLAYER_ACTION

    def test_get_recent_events(self, temp_db):
        """Test getting recent events in chronological order."""
        from dnd.database import create_game, add_event, get_recent_events

        game = create_game(chat_id=12345)
        add_event(game.id, 1, EventType.NARRATION, "First")
        add_event(game.id, 1, EventType.PLAYER_ACTION, "Second")
        add_event(game.id, 1, EventType.RESOLUTION, "Third")

        events = get_recent_events(game.id)
        assert len(events) == 3
        assert events[0].content == "First"
        assert events[1].content == "Second"
        assert events[2].content == "Third"

    def test_get_recent_events_limit(self, temp_db):
        """Test that event limit works correctly."""
        from dnd.database import create_game, add_event, get_recent_events

        game = create_game(chat_id=12345)
        for i in range(10):
            add_event(game.id, 1, EventType.SYSTEM, f"Event {i}")

        events = get_recent_events(game.id, limit=3)
        assert len(events) == 3
        # Should get the most recent 3, in chronological order
        assert events[0].content == "Event 7"
        assert events[1].content == "Event 8"
        assert events[2].content == "Event 9"

    def test_get_recent_events_empty(self, temp_db):
        """Test getting events when none exist."""
        from dnd.database import create_game, get_recent_events

        game = create_game(chat_id=12345)
        events = get_recent_events(game.id)
        assert events == []

    def test_all_event_types(self, temp_db):
        """Test that all event types are stored and retrieved correctly."""
        from dnd.database import create_game, add_event, get_recent_events

        game = create_game(chat_id=12345)
        for event_type in EventType:
            add_event(game.id, 1, event_type, f"Test {event_type.value}")

        events = get_recent_events(game.id)
        types = {e.event_type for e in events}
        assert types == set(EventType)
