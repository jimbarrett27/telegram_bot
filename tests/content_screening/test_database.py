"""Tests for content screening database operations."""

import sqlite3
import time
from unittest.mock import patch

import pytest

from content_screening.models import Article, SourceType


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test_content_screening.db"

    # Patch get_db_connection to use our temp database
    def get_test_connection():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn

    with patch("content_screening.database.get_db_connection", get_test_connection):
        # Import here to get patched version
        from content_screening.database import init_db
        init_db()
        yield get_test_connection


@pytest.fixture
def sample_article():
    """Create a sample article for testing."""
    return Article(
        external_id="test-article-123",
        source_type=SourceType.RSS,
        title="Test Article Title",
        abstract="This is a test abstract about drug safety.",
        url="https://example.com/article/123",
        authors=["John Smith", "Jane Doe"],
        categories=["Drug Safety Journal"],
        keywords_matched=["drug", "safety"],
        discovered_at=int(time.time()),
        llm_interest_score=0.8,
        llm_reasoning="Relevant to pharmacovigilance",
        llm_tags=["signal-detection", "nlp"],
        metadata={"feed_url": "https://example.com/rss"},
    )


@pytest.fixture
def sample_arxiv_article():
    """Create a sample ArXiv article for testing."""
    return Article(
        external_id="2401.12345",
        source_type=SourceType.ARXIV,
        title="Machine Learning for Adverse Event Detection",
        abstract="We present a novel approach...",
        url="https://arxiv.org/abs/2401.12345",
        authors=["Alice Brown"],
        categories=["cs.LG", "cs.CL"],
        keywords_matched=["adverse"],
        discovered_at=int(time.time()),
    )


class TestInitDb:
    """Tests for database initialization."""

    def test_creates_tables(self, temp_db):
        """Test that init_db creates all required tables."""
        conn = temp_db()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        conn.close()

        assert "articles" in tables
        assert "article_ratings" in tables
        assert "pending_article_notifications" in tables
        assert "scan_history" in tables

    def test_creates_indexes(self, temp_db):
        """Test that init_db creates indexes."""
        conn = temp_db()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        indexes = {row["name"] for row in cursor.fetchall()}
        conn.close()

        assert "idx_articles_source_type" in indexes
        assert "idx_articles_discovered_at" in indexes

    def test_idempotent(self, temp_db):
        """Test that init_db can be called multiple times safely."""
        from content_screening.database import init_db

        # Should not raise
        init_db()
        init_db()


class TestArticleOperations:
    """Tests for article CRUD operations."""

    def test_insert_article(self, temp_db, sample_article):
        """Test inserting an article."""
        from content_screening.database import insert_article, get_article_by_id

        article_id = insert_article(sample_article)

        assert article_id > 0

        retrieved = get_article_by_id(article_id)
        assert retrieved is not None
        assert retrieved.external_id == sample_article.external_id
        assert retrieved.title == sample_article.title
        assert retrieved.source_type == sample_article.source_type

    def test_insert_article_stores_all_fields(self, temp_db, sample_article):
        """Test that all article fields are stored correctly."""
        from content_screening.database import insert_article, get_article_by_id

        article_id = insert_article(sample_article)
        retrieved = get_article_by_id(article_id)

        assert retrieved.external_id == sample_article.external_id
        assert retrieved.source_type == sample_article.source_type
        assert retrieved.title == sample_article.title
        assert retrieved.abstract == sample_article.abstract
        assert retrieved.url == sample_article.url
        assert retrieved.authors == sample_article.authors
        assert retrieved.categories == sample_article.categories
        assert retrieved.keywords_matched == sample_article.keywords_matched
        assert retrieved.llm_interest_score == sample_article.llm_interest_score
        assert retrieved.llm_reasoning == sample_article.llm_reasoning
        assert retrieved.llm_tags == sample_article.llm_tags
        assert retrieved.metadata == sample_article.metadata

    def test_insert_article_minimal_fields(self, temp_db):
        """Test inserting an article with minimal fields."""
        from content_screening.database import insert_article, get_article_by_id

        article = Article(
            external_id="minimal-123",
            source_type=SourceType.RSS,
            title="Minimal Article",
            url="https://example.com/minimal",
        )

        article_id = insert_article(article)
        retrieved = get_article_by_id(article_id)

        assert retrieved is not None
        assert retrieved.title == "Minimal Article"
        assert retrieved.authors == []
        assert retrieved.categories == []
        assert retrieved.llm_interest_score is None

    def test_get_article_by_external_id(self, temp_db, sample_article):
        """Test retrieving an article by external ID."""
        from content_screening.database import (
            insert_article,
            get_article_by_external_id,
        )

        insert_article(sample_article)

        retrieved = get_article_by_external_id(
            sample_article.source_type,
            sample_article.external_id
        )

        assert retrieved is not None
        assert retrieved.title == sample_article.title

    def test_get_article_by_external_id_not_found(self, temp_db):
        """Test retrieving non-existent article returns None."""
        from content_screening.database import get_article_by_external_id

        result = get_article_by_external_id(SourceType.RSS, "nonexistent")
        assert result is None

    def test_get_article_by_id_not_found(self, temp_db):
        """Test retrieving non-existent article by ID returns None."""
        from content_screening.database import get_article_by_id

        result = get_article_by_id(99999)
        assert result is None

    def test_article_exists(self, temp_db, sample_article):
        """Test checking if an article exists."""
        from content_screening.database import insert_article, article_exists

        # Should not exist before insert
        assert not article_exists(
            sample_article.source_type,
            sample_article.external_id
        )

        insert_article(sample_article)

        # Should exist after insert
        assert article_exists(
            sample_article.source_type,
            sample_article.external_id
        )

    def test_article_exists_different_source_type(self, temp_db, sample_article):
        """Test that article_exists respects source_type."""
        from content_screening.database import insert_article, article_exists

        insert_article(sample_article)

        # Same external_id but different source_type should not exist
        assert not article_exists(
            SourceType.ARXIV,
            sample_article.external_id
        )

    def test_duplicate_article_raises(self, temp_db, sample_article):
        """Test that inserting duplicate article raises IntegrityError."""
        from content_screening.database import insert_article

        insert_article(sample_article)

        with pytest.raises(sqlite3.IntegrityError):
            insert_article(sample_article)

    def test_same_external_id_different_source(self, temp_db):
        """Test that same external_id with different source_type is allowed."""
        from content_screening.database import insert_article, article_exists

        article1 = Article(
            external_id="same-id",
            source_type=SourceType.RSS,
            title="RSS Article",
            url="https://rss.example.com/article",
        )
        article2 = Article(
            external_id="same-id",
            source_type=SourceType.ARXIV,
            title="ArXiv Article",
            url="https://arxiv.org/abs/same-id",
        )

        insert_article(article1)
        insert_article(article2)

        assert article_exists(SourceType.RSS, "same-id")
        assert article_exists(SourceType.ARXIV, "same-id")


class TestRatingOperations:
    """Tests for article rating operations."""

    def test_insert_rating(self, temp_db, sample_article):
        """Test inserting a rating."""
        from content_screening.database import (
            insert_article,
            insert_rating,
            get_ratings_for_article,
        )

        article_id = insert_article(sample_article)
        rating_id = insert_rating(article_id, 8)

        assert rating_id > 0

        ratings = get_ratings_for_article(article_id)
        assert len(ratings) == 1
        assert ratings[0].rating == 8
        assert ratings[0].article_id == article_id

    def test_multiple_ratings(self, temp_db, sample_article):
        """Test that multiple ratings can be stored for an article."""
        from content_screening.database import (
            insert_article,
            insert_rating,
            get_ratings_for_article,
        )

        article_id = insert_article(sample_article)

        insert_rating(article_id, 7)
        insert_rating(article_id, 9)
        insert_rating(article_id, 8)

        ratings = get_ratings_for_article(article_id)
        assert len(ratings) == 3
        # Should be ordered by rated_at DESC (most recent first)
        rating_values = [r.rating for r in ratings]
        assert set(rating_values) == {7, 8, 9}

    def test_get_ratings_empty(self, temp_db, sample_article):
        """Test getting ratings for article with no ratings."""
        from content_screening.database import (
            insert_article,
            get_ratings_for_article,
        )

        article_id = insert_article(sample_article)
        ratings = get_ratings_for_article(article_id)

        assert ratings == []


class TestNotificationOperations:
    """Tests for pending notification operations."""

    def test_create_pending_notification(self, temp_db, sample_article):
        """Test creating a pending notification."""
        from content_screening.database import (
            insert_article,
            create_pending_notification,
            get_pending_notifications,
        )

        article_id = insert_article(sample_article)
        notification_id = create_pending_notification(article_id)

        assert notification_id > 0

        pending = get_pending_notifications()
        assert len(pending) == 1
        assert pending[0].article_id == article_id
        assert pending[0].rating_received is False

    def test_get_oldest_pending_notification(self, temp_db):
        """Test getting the oldest pending notification."""
        from content_screening.database import (
            insert_article,
            create_pending_notification,
            get_oldest_pending_notification,
        )

        # Create multiple articles and notifications
        article1 = Article(
            external_id="first",
            source_type=SourceType.RSS,
            title="First Article",
            url="https://example.com/first",
        )
        article2 = Article(
            external_id="second",
            source_type=SourceType.RSS,
            title="Second Article",
            url="https://example.com/second",
        )

        id1 = insert_article(article1)
        create_pending_notification(id1)

        time.sleep(0.01)  # Ensure different timestamps

        id2 = insert_article(article2)
        create_pending_notification(id2)

        oldest = get_oldest_pending_notification()
        assert oldest is not None
        assert oldest.article_id == id1

    def test_get_oldest_pending_notification_empty(self, temp_db):
        """Test getting oldest notification when none exist."""
        from content_screening.database import get_oldest_pending_notification

        result = get_oldest_pending_notification()
        assert result is None

    def test_mark_notification_rated(self, temp_db, sample_article):
        """Test marking a notification as rated."""
        from content_screening.database import (
            insert_article,
            create_pending_notification,
            mark_notification_rated,
            get_pending_notifications,
            get_oldest_pending_notification,
        )

        article_id = insert_article(sample_article)
        create_pending_notification(article_id)

        # Should have one pending
        assert len(get_pending_notifications()) == 1

        notification = get_oldest_pending_notification()
        mark_notification_rated(notification.id)

        # Should have no pending after marking as rated
        assert len(get_pending_notifications()) == 0

    def test_duplicate_notification_ignored(self, temp_db, sample_article):
        """Test that creating duplicate notification is ignored."""
        from content_screening.database import (
            insert_article,
            create_pending_notification,
            get_pending_notifications,
        )

        article_id = insert_article(sample_article)

        create_pending_notification(article_id)
        create_pending_notification(article_id)  # Duplicate

        # Should still only have one
        pending = get_pending_notifications()
        assert len(pending) == 1


class TestScanHistoryOperations:
    """Tests for scan history operations."""

    def test_update_scan_history(self, temp_db):
        """Test updating scan history."""
        from content_screening.database import (
            update_scan_history,
            get_last_scan_time,
        )

        before = int(time.time())
        update_scan_history(SourceType.ARXIV, articles_found=10, articles_interesting=3)
        after = int(time.time())

        last_scan = get_last_scan_time(SourceType.ARXIV)
        assert last_scan is not None
        assert before <= last_scan <= after

    def test_get_last_scan_time_not_found(self, temp_db):
        """Test getting scan time for source that hasn't been scanned."""
        from content_screening.database import get_last_scan_time

        result = get_last_scan_time(SourceType.BLOG)
        assert result is None

    def test_update_scan_history_overwrites(self, temp_db):
        """Test that update_scan_history overwrites previous entry."""
        from content_screening.database import (
            update_scan_history,
            get_last_scan_time,
        )

        update_scan_history(SourceType.RSS, articles_found=5, articles_interesting=1)
        first_scan = get_last_scan_time(SourceType.RSS)

        time.sleep(0.01)

        update_scan_history(SourceType.RSS, articles_found=10, articles_interesting=2)
        second_scan = get_last_scan_time(SourceType.RSS)

        assert second_scan >= first_scan

    def test_scan_history_per_source_type(self, temp_db):
        """Test that scan history is tracked separately per source type."""
        from content_screening.database import (
            update_scan_history,
            get_last_scan_time,
        )

        update_scan_history(SourceType.ARXIV, articles_found=10, articles_interesting=3)

        time.sleep(0.01)

        update_scan_history(SourceType.RSS, articles_found=20, articles_interesting=5)

        arxiv_time = get_last_scan_time(SourceType.ARXIV)
        rss_time = get_last_scan_time(SourceType.RSS)

        assert arxiv_time is not None
        assert rss_time is not None
        assert rss_time >= arxiv_time


class TestRowConversion:
    """Tests for database row to model conversion."""

    def test_article_with_empty_json_fields(self, temp_db):
        """Test that empty JSON fields are handled correctly."""
        from content_screening.database import insert_article, get_article_by_id

        article = Article(
            external_id="empty-fields",
            source_type=SourceType.RSS,
            title="Article with empty fields",
            url="https://example.com/empty",
            authors=[],
            categories=[],
            keywords_matched=[],
            llm_tags=[],
            metadata={},
        )

        article_id = insert_article(article)
        retrieved = get_article_by_id(article_id)

        assert retrieved.authors == []
        assert retrieved.categories == []
        assert retrieved.keywords_matched == []
        assert retrieved.llm_tags == []
        assert retrieved.metadata == {}

    def test_article_with_special_characters(self, temp_db):
        """Test handling of special characters in article fields."""
        from content_screening.database import insert_article, get_article_by_id

        article = Article(
            external_id="special-chars",
            source_type=SourceType.RSS,
            title='Test with émojis 🎉 and "quotes"',
            abstract="Abstract with\nnewlines\tand\ttabs",
            url="https://example.com/special?param=value&other=1",
            authors=["José García", "François Müller"],
        )

        article_id = insert_article(article)
        retrieved = get_article_by_id(article_id)

        assert retrieved.title == article.title
        assert retrieved.abstract == article.abstract
        assert retrieved.authors == article.authors
