"""
Database operations for the content screening system.
"""

import json
import sqlite3
import time
from typing import List, Optional

from content_screening.constants import DB_NAME
from content_screening.models import Article, ArticleRating, PendingNotification, SourceType


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database schema."""
    conn = get_db_connection()
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                title TEXT NOT NULL,
                abstract TEXT,
                url TEXT NOT NULL,
                authors TEXT,
                categories TEXT,
                keywords_matched TEXT,
                discovered_at INTEGER NOT NULL,
                llm_interest_score REAL,
                llm_reasoning TEXT,
                embedding BLOB,
                metadata TEXT,
                UNIQUE(source_type, external_id)
            )
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_articles_source_type
            ON articles(source_type)
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_articles_discovered_at
            ON articles(discovered_at)
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS article_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                rated_at INTEGER NOT NULL,
                FOREIGN KEY (article_id) REFERENCES articles(id)
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS pending_article_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                notified_at INTEGER NOT NULL,
                rating_received INTEGER DEFAULT 0,
                FOREIGN KEY (article_id) REFERENCES articles(id),
                UNIQUE(article_id)
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS scan_history (
                source_type TEXT PRIMARY KEY,
                last_scan_epoch INTEGER NOT NULL,
                articles_found INTEGER DEFAULT 0,
                articles_interesting INTEGER DEFAULT 0
            )
        ''')
    conn.close()


def _row_to_article(row) -> Article:
    """Convert a database row to an Article object."""
    return Article(
        id=row['id'],
        external_id=row['external_id'],
        source_type=SourceType(row['source_type']),
        title=row['title'],
        abstract=row['abstract'],
        url=row['url'],
        authors=json.loads(row['authors']) if row['authors'] else [],
        categories=json.loads(row['categories']) if row['categories'] else [],
        keywords_matched=json.loads(row['keywords_matched']) if row['keywords_matched'] else [],
        discovered_at=row['discovered_at'],
        llm_interest_score=row['llm_interest_score'],
        llm_reasoning=row['llm_reasoning'],
        embedding=row['embedding'],
        metadata=json.loads(row['metadata']) if row['metadata'] else {},
    )


def _row_to_rating(row) -> ArticleRating:
    """Convert a database row to an ArticleRating object."""
    return ArticleRating(
        id=row['id'],
        article_id=row['article_id'],
        rating=row['rating'],
        rated_at=row['rated_at'],
    )


def _row_to_pending_notification(row) -> PendingNotification:
    """Convert a database row to a PendingNotification object."""
    return PendingNotification(
        id=row['id'],
        article_id=row['article_id'],
        notified_at=row['notified_at'],
        rating_received=bool(row['rating_received']),
    )


def insert_article(article: Article) -> int:
    """Insert a new article into the database.

    Returns the article id.
    """
    conn = get_db_connection()
    with conn:
        cursor = conn.execute('''
            INSERT INTO articles (
                external_id, source_type, title, abstract, url,
                authors, categories, keywords_matched, discovered_at,
                llm_interest_score, llm_reasoning, embedding, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            article.external_id,
            article.source_type.value,
            article.title,
            article.abstract,
            article.url,
            json.dumps(article.authors) if article.authors else None,
            json.dumps(article.categories) if article.categories else None,
            json.dumps(article.keywords_matched) if article.keywords_matched else None,
            article.discovered_at or int(time.time()),
            article.llm_interest_score,
            article.llm_reasoning,
            article.embedding,
            json.dumps(article.metadata) if article.metadata else None,
        ))
        article_id = cursor.lastrowid
    conn.close()
    return article_id


def get_article_by_external_id(source_type: SourceType, external_id: str) -> Optional[Article]:
    """Get an article by its external ID and source type."""
    conn = get_db_connection()
    cursor = conn.execute('''
        SELECT * FROM articles
        WHERE source_type = ? AND external_id = ?
    ''', (source_type.value, external_id))
    row = cursor.fetchone()
    conn.close()
    return _row_to_article(row) if row else None


def get_article_by_id(article_id: int) -> Optional[Article]:
    """Get an article by its database ID."""
    conn = get_db_connection()
    cursor = conn.execute('''
        SELECT * FROM articles WHERE id = ?
    ''', (article_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_article(row) if row else None


def article_exists(source_type: SourceType, external_id: str) -> bool:
    """Check if an article already exists in the database."""
    conn = get_db_connection()
    cursor = conn.execute('''
        SELECT 1 FROM articles
        WHERE source_type = ? AND external_id = ?
    ''', (source_type.value, external_id))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def insert_rating(article_id: int, rating: int) -> int:
    """Insert a rating for an article.

    Returns the rating id.
    """
    conn = get_db_connection()
    with conn:
        cursor = conn.execute('''
            INSERT INTO article_ratings (article_id, rating, rated_at)
            VALUES (?, ?, ?)
        ''', (article_id, rating, int(time.time())))
        rating_id = cursor.lastrowid
    conn.close()
    return rating_id


def get_ratings_for_article(article_id: int) -> List[ArticleRating]:
    """Get all ratings for an article."""
    conn = get_db_connection()
    cursor = conn.execute('''
        SELECT * FROM article_ratings
        WHERE article_id = ?
        ORDER BY rated_at DESC
    ''', (article_id,))
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_rating(row) for row in rows]


def create_pending_notification(article_id: int) -> int:
    """Create a pending notification for an article.

    Returns the notification id.
    """
    conn = get_db_connection()
    with conn:
        cursor = conn.execute('''
            INSERT OR IGNORE INTO pending_article_notifications (article_id, notified_at)
            VALUES (?, ?)
        ''', (article_id, int(time.time())))
        notification_id = cursor.lastrowid
    conn.close()
    return notification_id


def get_pending_notifications() -> List[PendingNotification]:
    """Get all notifications awaiting a rating."""
    conn = get_db_connection()
    cursor = conn.execute('''
        SELECT * FROM pending_article_notifications
        WHERE rating_received = 0
        ORDER BY notified_at ASC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_pending_notification(row) for row in rows]


def get_oldest_pending_notification() -> Optional[PendingNotification]:
    """Get the oldest notification awaiting a rating."""
    conn = get_db_connection()
    cursor = conn.execute('''
        SELECT * FROM pending_article_notifications
        WHERE rating_received = 0
        ORDER BY notified_at ASC
        LIMIT 1
    ''')
    row = cursor.fetchone()
    conn.close()
    return _row_to_pending_notification(row) if row else None


def mark_notification_rated(notification_id: int):
    """Mark a notification as having received a rating."""
    conn = get_db_connection()
    with conn:
        conn.execute('''
            UPDATE pending_article_notifications
            SET rating_received = 1
            WHERE id = ?
        ''', (notification_id,))
    conn.close()


def get_last_scan_time(source_type: SourceType) -> Optional[int]:
    """Get the last scan time for a source type."""
    conn = get_db_connection()
    cursor = conn.execute('''
        SELECT last_scan_epoch FROM scan_history
        WHERE source_type = ?
    ''', (source_type.value,))
    row = cursor.fetchone()
    conn.close()
    return row['last_scan_epoch'] if row else None


def update_scan_history(source_type: SourceType, articles_found: int = 0, articles_interesting: int = 0):
    """Update the scan history for a source type."""
    conn = get_db_connection()
    with conn:
        conn.execute('''
            INSERT INTO scan_history (source_type, last_scan_epoch, articles_found, articles_interesting)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(source_type) DO UPDATE SET
                last_scan_epoch = excluded.last_scan_epoch,
                articles_found = excluded.articles_found,
                articles_interesting = excluded.articles_interesting
        ''', (source_type.value, int(time.time()), articles_found, articles_interesting))
    conn.close()
