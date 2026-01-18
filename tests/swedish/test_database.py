"""Tests for Swedish flashcards database operations."""

import time

import pytest
from sqlalchemy import create_engine

from swedish import db_engine
from swedish.flash_card import FlashCard, WordType
from swedish.orm_models import Base


@pytest.fixture
def temp_db():
    """Create a temporary in-memory database for testing."""
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)
    db_engine.set_engine(test_engine)
    yield test_engine
    db_engine.reset_engine()


@pytest.fixture
def sample_card():
    """Create a sample flashcard for testing."""
    return FlashCard(
        word_to_learn="hund",
        word_type=WordType.NOUN,
        n_times_seen=5,
        difficulty=0.3,
        stability=2.5,
        last_review_epoch=int(time.time()) - 86400,
        next_review_min_epoch=int(time.time()) - 3600,
    )


class TestInitDb:
    """Tests for database initialization."""

    def test_creates_table(self, temp_db):
        """Test that init_db creates the flashcards table."""
        from sqlalchemy import text

        with temp_db.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            tables = {row[0] for row in result.fetchall()}

        assert "flashcards" in tables

    def test_idempotent(self, temp_db):
        """Test that init_db can be called multiple times safely."""
        from swedish.database import init_db

        # Should not raise
        init_db()
        init_db()


class TestCardOperations:
    """Tests for flashcard CRUD operations."""

    def test_add_card(self, temp_db):
        """Test adding a flashcard."""
        from swedish.database import add_card, get_card

        add_card("katt", WordType.NOUN)

        card = get_card("katt")
        assert card is not None
        assert card.word_to_learn == "katt"
        assert card.word_type == WordType.NOUN
        assert card.n_times_seen == 0
        assert card.difficulty == 0.0
        assert card.stability == 0.0

    def test_add_card_default_word_type(self, temp_db):
        """Test adding a card with default word type."""
        from swedish.database import add_card, get_card

        add_card("test")

        card = get_card("test")
        assert card is not None
        assert card.word_type == WordType.UNKNOWN

    def test_add_duplicate_card_ignored(self, temp_db):
        """Test that adding duplicate card is ignored."""
        from swedish.database import add_card, get_card

        add_card("hund", WordType.NOUN)
        add_card("hund", WordType.VERB)  # Try to add again with different type

        card = get_card("hund")
        assert card is not None
        assert card.word_type == WordType.NOUN  # Original type preserved

    def test_get_card_not_found(self, temp_db):
        """Test getting non-existent card returns None."""
        from swedish.database import get_card

        result = get_card("nonexistent")
        assert result is None

    def test_update_card(self, temp_db, sample_card):
        """Test updating a flashcard."""
        from swedish.database import add_card, get_card, update_card

        add_card(sample_card.word_to_learn, sample_card.word_type)

        # Update the card
        card = get_card(sample_card.word_to_learn)
        card.n_times_seen = 10
        card.difficulty = 0.5
        card.stability = 5.0
        update_card(card)

        # Verify update
        updated = get_card(sample_card.word_to_learn)
        assert updated.n_times_seen == 10
        assert updated.difficulty == 0.5
        assert updated.stability == 5.0


class TestDueCards:
    """Tests for due card operations."""

    def test_get_due_cards(self, temp_db):
        """Test getting cards that are due for review."""
        from swedish.database import add_card, get_card, update_card, get_due_cards

        # Add cards with different due times
        add_card("past_due", WordType.NOUN)
        add_card("future_due", WordType.NOUN)

        current_time = int(time.time())

        # Make one card past due
        card1 = get_card("past_due")
        card1.next_review_min_epoch = current_time - 3600
        update_card(card1)

        # Make one card future due
        card2 = get_card("future_due")
        card2.next_review_min_epoch = current_time + 3600
        update_card(card2)

        due_cards = get_due_cards()
        words = [c.word_to_learn for c in due_cards]

        assert "past_due" in words
        assert "future_due" not in words

    def test_get_next_due_card(self, temp_db):
        """Test getting the next card due for review."""
        from swedish.database import add_card, get_card, update_card, get_next_due_card

        add_card("first", WordType.NOUN)
        add_card("second", WordType.NOUN)

        # Set different due times
        card1 = get_card("first")
        card1.next_review_min_epoch = 100
        update_card(card1)

        card2 = get_card("second")
        card2.next_review_min_epoch = 50
        update_card(card2)

        next_card = get_next_due_card()
        assert next_card is not None
        assert next_card.word_to_learn == "second"

    def test_get_next_due_card_empty(self, temp_db):
        """Test getting next due card when database is empty."""
        from swedish.database import get_next_due_card

        result = get_next_due_card()
        assert result is None


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_get_all_words(self, temp_db):
        """Test getting all words."""
        from swedish.database import add_card, get_all_words

        add_card("ett", WordType.NOUN)
        add_card("två", WordType.NOUN)
        add_card("tre", WordType.NOUN)

        words = get_all_words()
        assert len(words) == 3
        assert set(words) == {"ett", "två", "tre"}

    def test_get_all_words_empty(self, temp_db):
        """Test getting words from empty database."""
        from swedish.database import get_all_words

        words = get_all_words()
        assert words == []

    def test_count_cards(self, temp_db):
        """Test counting cards."""
        from swedish.database import add_card, count_cards

        assert count_cards() == 0

        add_card("one", WordType.NOUN)
        assert count_cards() == 1

        add_card("two", WordType.VERB)
        add_card("three", WordType.ADJECTIVE)
        assert count_cards() == 3


class TestWordTypes:
    """Tests for word type handling."""

    def test_all_word_types(self, temp_db):
        """Test that all word types are stored and retrieved correctly."""
        from swedish.database import add_card, get_card

        for word_type in WordType:
            word = f"test_{word_type.name.lower()}"
            add_card(word, word_type)

            card = get_card(word)
            assert card is not None
            assert card.word_type == word_type
