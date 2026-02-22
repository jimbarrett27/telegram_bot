"""Tests for DM memory persistence: notes CRUD, story summary, and summarizer."""

from unittest.mock import patch, MagicMock

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


class TestDmNotes:
    """Tests for DM note CRUD operations."""

    def test_add_dm_note(self, temp_db):
        from dnd.database import create_game, add_dm_note

        game = create_game(chat_id=12345)
        note = add_dm_note(game.id, "The innkeeper is secretly a dragon")

        assert note is not None
        assert note.id is not None
        assert note.game_id == game.id
        assert note.content == "The innkeeper is secretly a dragon"
        assert note.created_at > 0

    def test_get_dm_notes_empty(self, temp_db):
        from dnd.database import create_game, get_dm_notes

        game = create_game(chat_id=12345)
        notes = get_dm_notes(game.id)
        assert notes == []

    def test_get_dm_notes_ordered(self, temp_db):
        from dnd.database import create_game, add_dm_note, get_dm_notes

        game = create_game(chat_id=12345)
        add_dm_note(game.id, "First note")
        add_dm_note(game.id, "Second note")
        add_dm_note(game.id, "Third note")

        notes = get_dm_notes(game.id)
        assert len(notes) == 3
        assert notes[0].content == "First note"
        assert notes[1].content == "Second note"
        assert notes[2].content == "Third note"

    def test_dm_notes_isolated_per_game(self, temp_db):
        from dnd.database import create_game, add_dm_note, get_dm_notes

        game1 = create_game(chat_id=11111)
        game2 = create_game(chat_id=22222)
        add_dm_note(game1.id, "Note for game 1")
        add_dm_note(game2.id, "Note for game 2")

        notes1 = get_dm_notes(game1.id)
        notes2 = get_dm_notes(game2.id)
        assert len(notes1) == 1
        assert len(notes2) == 1
        assert notes1[0].content == "Note for game 1"
        assert notes2[0].content == "Note for game 2"

    def test_delete_game_cleans_up_notes(self, temp_db):
        from dnd.database import create_game, add_dm_note, get_dm_notes, delete_game

        game = create_game(chat_id=12345)
        add_dm_note(game.id, "A note")
        add_dm_note(game.id, "Another note")

        delete_game(12345)
        # Notes should be gone (game is gone, so querying by game_id returns empty)
        notes = get_dm_notes(game.id)
        assert notes == []


class TestStorySummary:
    """Tests for story summary storage and retrieval."""

    def test_default_story_summary_empty(self, temp_db):
        from dnd.database import create_game, get_story_summary

        game = create_game(chat_id=12345)
        summary = get_story_summary(game.id)
        assert summary == ""

    def test_update_and_get_story_summary(self, temp_db):
        from dnd.database import create_game, update_story_summary, get_story_summary

        game = create_game(chat_id=12345)
        update_story_summary(game.id, "The party entered the dungeon.")

        summary = get_story_summary(game.id)
        assert summary == "The party entered the dungeon."

    def test_story_summary_in_game_dataclass(self, temp_db):
        from dnd.database import create_game, update_story_summary, get_game_by_chat

        game = create_game(chat_id=12345)
        update_story_summary(game.id, "Adventure summary here.")

        loaded = get_game_by_chat(12345)
        assert loaded.story_summary == "Adventure summary here."

    def test_story_summary_overwrites(self, temp_db):
        from dnd.database import create_game, update_story_summary, get_story_summary

        game = create_game(chat_id=12345)
        update_story_summary(game.id, "First summary")
        update_story_summary(game.id, "Updated summary")

        summary = get_story_summary(game.id)
        assert summary == "Updated summary"

    def test_get_story_summary_nonexistent_game(self, temp_db):
        from dnd.database import get_story_summary

        summary = get_story_summary(99999)
        assert summary == ""


class TestSummarizer:
    """Tests for the event summarizer (LLM mocked)."""

    def test_summarize_events_calls_llm(self, temp_db):
        from dnd.database import create_game, add_event, get_story_summary
        from dnd.summarizer import summarize_events

        game = create_game(chat_id=12345)
        add_event(game.id, 1, EventType.NARRATION, "You enter a dark cave.")
        add_event(game.id, 1, EventType.PLAYER_ACTION, "I light a torch.")
        add_event(game.id, 1, EventType.RESOLUTION, "The cave is illuminated.")

        mock_response = MagicMock()
        mock_response.content = "The party entered a dark cave and lit a torch."

        with patch("dnd.summarizer.ChatGoogleGenerativeAI") as mock_llm_cls, \
             patch("dnd.summarizer.get_gemini_api_key", return_value="fake-key"):
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_cls.return_value = mock_llm

            result = summarize_events(game.id)

        assert result == "The party entered a dark cave and lit a torch."
        assert get_story_summary(game.id) == "The party entered a dark cave and lit a torch."
        mock_llm.invoke.assert_called_once()

    def test_summarize_events_no_events(self, temp_db):
        from dnd.database import create_game, get_story_summary
        from dnd.summarizer import summarize_events

        game = create_game(chat_id=12345)

        with patch("dnd.summarizer.ChatGoogleGenerativeAI"), \
             patch("dnd.summarizer.get_gemini_api_key", return_value="fake-key"):
            result = summarize_events(game.id)

        assert result == ""
        assert get_story_summary(game.id) == ""

    def test_summarize_events_includes_existing_summary(self, temp_db):
        from dnd.database import create_game, add_event, update_story_summary
        from dnd.summarizer import summarize_events

        game = create_game(chat_id=12345)
        update_story_summary(game.id, "Previous summary.")
        add_event(game.id, 2, EventType.RESOLUTION, "New event happened.")

        mock_response = MagicMock()
        mock_response.content = "Updated summary."

        with patch("dnd.summarizer.ChatGoogleGenerativeAI") as mock_llm_cls, \
             patch("dnd.summarizer.get_gemini_api_key", return_value="fake-key"):
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_cls.return_value = mock_llm

            summarize_events(game.id)

            # Verify the prompt includes existing summary
            call_args = mock_llm.invoke.call_args[0][0]
            prompt_text = call_args[0].content
            assert "Previous summary." in prompt_text


class TestMemoryTools:
    """Tests for the MemoryTools LangChain tool wrappers."""

    def test_write_note_tool(self, temp_db):
        from dnd.database import create_game, get_dm_notes
        from dnd.memory_tools import MemoryTools

        game = create_game(chat_id=12345)
        tools = MemoryTools(game.id).as_tools()
        write_note = tools[0]

        result = write_note.invoke({"note": "The goblin king is named Gruk"})
        assert "Note recorded" in result

        notes = get_dm_notes(game.id)
        assert len(notes) == 1
        assert notes[0].content == "The goblin king is named Gruk"

    def test_read_notes_tool_empty(self, temp_db):
        from dnd.database import create_game
        from dnd.memory_tools import MemoryTools

        game = create_game(chat_id=12345)
        tools = MemoryTools(game.id).as_tools()
        read_notes = tools[1]

        result = read_notes.invoke({})
        assert "No notes recorded" in result

    def test_read_notes_tool_with_notes(self, temp_db):
        from dnd.database import create_game, add_dm_note
        from dnd.memory_tools import MemoryTools

        game = create_game(chat_id=12345)
        add_dm_note(game.id, "Fact one")
        add_dm_note(game.id, "Fact two")

        tools = MemoryTools(game.id).as_tools()
        read_notes = tools[1]

        result = read_notes.invoke({})
        assert "Fact one" in result
        assert "Fact two" in result
