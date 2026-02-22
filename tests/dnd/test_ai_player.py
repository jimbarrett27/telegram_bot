"""Tests for AI player agent, turn timeout detection, and is_ai flag."""

import time
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from sqlalchemy import create_engine

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


class TestIsAiFlag:
    """Tests for the is_ai player flag."""

    def test_default_is_human(self, temp_db):
        from dnd.database import create_game, add_player, get_player_by_id

        game = create_game(chat_id=12345)
        player = add_player(
            game.id, 111, "alice", "Alara", CharacterClass.WARRIOR
        )

        fetched = get_player_by_id(player.id)
        assert fetched.is_ai is False

    def test_add_ai_player(self, temp_db):
        from dnd.database import create_game, add_player, get_player_by_id

        game = create_game(chat_id=12345)
        player = add_player(
            game.id, -999, "AI_Bot", "Botrick", CharacterClass.CLERIC, is_ai=True
        )

        fetched = get_player_by_id(player.id)
        assert fetched.is_ai is True
        assert fetched.character_name == "Botrick"

    def test_ai_flag_in_game_players(self, temp_db):
        from dnd.database import create_game, add_player, get_game_by_chat

        game = create_game(chat_id=12345)
        add_player(game.id, 111, "alice", "Alara", CharacterClass.WARRIOR)
        add_player(game.id, -999, "AI_Bot", "Botrick", CharacterClass.CLERIC, is_ai=True)

        loaded = get_game_by_chat(12345)
        assert len(loaded.players) == 2
        ai_players = [p for p in loaded.players if p.is_ai]
        human_players = [p for p in loaded.players if not p.is_ai]
        assert len(ai_players) == 1
        assert len(human_players) == 1
        assert ai_players[0].character_name == "Botrick"


class TestStaleActiveGames:
    """Tests for detecting games with timed-out turns."""

    def test_no_stale_games(self, temp_db):
        from dnd.database import create_game, get_stale_active_games, update_game_status

        game = create_game(chat_id=12345)
        update_game_status(game.id, GameStatus.ACTIVE)

        # Game was just updated, so it shouldn't be stale
        stale = get_stale_active_games(timeout_seconds=86400)
        assert stale == []

    def test_detects_stale_game(self, temp_db):
        from dnd.database import create_game, get_stale_active_games, update_game_status
        from dnd.orm_models import GameORM
        from dnd.db_engine import get_session

        game = create_game(chat_id=12345)
        update_game_status(game.id, GameStatus.ACTIVE)

        # Manually set updated_at to 25 hours ago
        old_time = int(time.time()) - 90000
        with get_session() as session:
            orm = session.get(GameORM, game.id)
            orm.updated_at = old_time

        stale = get_stale_active_games(timeout_seconds=86400)
        assert len(stale) == 1
        assert stale[0].id == game.id

    def test_ignores_recruiting_games(self, temp_db):
        from dnd.database import create_game, get_stale_active_games
        from dnd.orm_models import GameORM
        from dnd.db_engine import get_session

        game = create_game(chat_id=12345)  # Status: RECRUITING

        # Make it old
        old_time = int(time.time()) - 90000
        with get_session() as session:
            orm = session.get(GameORM, game.id)
            orm.updated_at = old_time

        stale = get_stale_active_games(timeout_seconds=86400)
        assert stale == []

    def test_stale_game_includes_players(self, temp_db):
        from dnd.database import (
            create_game, add_player, get_stale_active_games, update_game_status,
        )
        from dnd.orm_models import GameORM
        from dnd.db_engine import get_session

        game = create_game(chat_id=12345)
        add_player(game.id, 111, "alice", "Alara", CharacterClass.WARRIOR)
        update_game_status(game.id, GameStatus.ACTIVE)

        old_time = int(time.time()) - 90000
        with get_session() as session:
            orm = session.get(GameORM, game.id)
            orm.updated_at = old_time

        stale = get_stale_active_games(timeout_seconds=86400)
        assert len(stale) == 1
        assert len(stale[0].players) == 1
        assert stale[0].players[0].character_name == "Alara"


class TestGenerateAiAction:
    """Tests for AI action generation (LLM mocked)."""

    def test_generates_action(self, temp_db):
        from dnd.database import create_game, add_player, add_event
        from dnd.ai_player import generate_ai_action

        game = create_game(chat_id=12345)
        player = add_player(
            game.id, 111, "alice", "Alara", CharacterClass.WARRIOR
        )
        add_event(game.id, 1, EventType.NARRATION, "You see a goblin.")

        mock_response = MagicMock()
        mock_response.content = "I draw my longsword and attack the goblin!"

        with patch("dnd.ai_player.ChatGoogleGenerativeAI") as mock_llm_cls, \
             patch("dnd.ai_player.get_gemini_api_key", return_value="fake-key"):
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_cls.return_value = mock_llm

            action = generate_ai_action(game.id, player.id)

        assert action == "I draw my longsword and attack the goblin!"
        mock_llm.invoke.assert_called_once()

    def test_fallback_on_missing_game(self, temp_db):
        from dnd.ai_player import generate_ai_action

        action = generate_ai_action(99999, 99999)
        assert action == "I look around cautiously."

    def test_prompt_includes_character_info(self, temp_db):
        from dnd.database import create_game, add_player
        from dnd.ai_player import generate_ai_action

        game = create_game(chat_id=12345)
        player = add_player(
            game.id, 111, "alice", "Alara", CharacterClass.MAGE,
            intelligence=16,
        )

        mock_response = MagicMock()
        mock_response.content = "I cast a spell."

        with patch("dnd.ai_player.ChatGoogleGenerativeAI") as mock_llm_cls, \
             patch("dnd.ai_player.get_gemini_api_key", return_value="fake-key"):
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_cls.return_value = mock_llm

            generate_ai_action(game.id, player.id)

            # Verify prompt contains character details
            call_args = mock_llm.invoke.call_args[0][0]
            prompt_text = call_args[0].content
            assert "Alara" in prompt_text
            assert "Mage" in prompt_text
            assert "INT:16" in prompt_text


class TestGenerateAiClarificationResponse:
    """Tests for AI clarification response generation."""

    def test_generates_response(self, temp_db):
        from dnd.database import create_game, add_player
        from dnd.ai_player import generate_ai_clarification_response

        game = create_game(chat_id=12345)
        player = add_player(
            game.id, 111, "alice", "Alara", CharacterClass.WARRIOR
        )

        mock_response = MagicMock()
        mock_response.content = "The goblin by the door."

        with patch("dnd.ai_player.ChatGoogleGenerativeAI") as mock_llm_cls, \
             patch("dnd.ai_player.get_gemini_api_key", return_value="fake-key"):
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_cls.return_value = mock_llm

            result = generate_ai_clarification_response(
                game.id, player.id, "Which goblin do you attack?"
            )

        assert result == "The goblin by the door."

    def test_fallback_on_missing_player(self, temp_db):
        from dnd.ai_player import generate_ai_clarification_response

        result = generate_ai_clarification_response(99999, 99999, "question?")
        assert "whatever seems best" in result
