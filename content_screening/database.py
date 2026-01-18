"""
Database operations for the content screening system.

Uses SQLAlchemy ORM for database access. The public API uses dataclass models
from models.py, with conversion to/from ORM models handled internally.
"""

import time
from typing import List, Optional

from sqlalchemy import select, exists

from content_screening.db_engine import get_engine, get_session
from content_screening.models import Article, ArticleRating, PendingNotification, SourceType
from content_screening.orm_models import (
    Base,
    ArticleORM,
    ArticleRatingORM,
    PendingNotificationORM,
    ScanHistoryORM,
    article_orm_to_dataclass,
    article_dataclass_to_orm,
    rating_orm_to_dataclass,
    notification_orm_to_dataclass,
)


def init_db():
    """Initialize the database schema."""
    engine = get_engine()
    Base.metadata.create_all(engine)


def insert_article(article: Article) -> int:
    """Insert a new article into the database.

    Returns the article id.
    """
    discovered_at = article.discovered_at or int(time.time())
    orm = article_dataclass_to_orm(article, discovered_at)

    with get_session() as session:
        session.add(orm)
        session.flush()
        return orm.id


def get_article_by_external_id(source_type: SourceType, external_id: str) -> Optional[Article]:
    """Get an article by its external ID and source type."""
    with get_session() as session:
        stmt = select(ArticleORM).where(
            ArticleORM.source_type == source_type.value,
            ArticleORM.external_id == external_id,
        )
        orm = session.execute(stmt).scalar_one_or_none()
        if orm is None:
            return None
        return article_orm_to_dataclass(orm)


def get_article_by_id(article_id: int) -> Optional[Article]:
    """Get an article by its database ID."""
    with get_session() as session:
        orm = session.get(ArticleORM, article_id)
        if orm is None:
            return None
        return article_orm_to_dataclass(orm)


def article_exists(source_type: SourceType, external_id: str) -> bool:
    """Check if an article already exists in the database."""
    with get_session() as session:
        stmt = select(
            exists().where(
                ArticleORM.source_type == source_type.value,
                ArticleORM.external_id == external_id,
            )
        )
        return session.execute(stmt).scalar()


def insert_rating(article_id: int, rating: int) -> int:
    """Insert a rating for an article.

    Returns the rating id.
    """
    orm = ArticleRatingORM(
        article_id=article_id,
        rating=rating,
        rated_at=int(time.time()),
    )

    with get_session() as session:
        session.add(orm)
        session.flush()
        return orm.id


def get_ratings_for_article(article_id: int) -> List[ArticleRating]:
    """Get all ratings for an article."""
    with get_session() as session:
        stmt = (
            select(ArticleRatingORM)
            .where(ArticleRatingORM.article_id == article_id)
            .order_by(ArticleRatingORM.rated_at.desc())
        )
        orms = session.execute(stmt).scalars().all()
        return [rating_orm_to_dataclass(orm) for orm in orms]


def create_pending_notification(article_id: int) -> int:
    """Create a pending notification for an article.

    Returns the notification id. If notification already exists, returns 0.
    """
    with get_session() as session:
        # Check if notification already exists (equivalent to INSERT OR IGNORE)
        stmt = select(PendingNotificationORM).where(
            PendingNotificationORM.article_id == article_id
        )
        existing = session.execute(stmt).scalar_one_or_none()
        if existing is not None:
            return 0

        orm = PendingNotificationORM(
            article_id=article_id,
            notified_at=int(time.time()),
            rating_received=0,
        )
        session.add(orm)
        session.flush()
        return orm.id


def get_pending_notifications() -> List[PendingNotification]:
    """Get all notifications awaiting a rating."""
    with get_session() as session:
        stmt = (
            select(PendingNotificationORM)
            .where(PendingNotificationORM.rating_received == 0)
            .order_by(PendingNotificationORM.notified_at.asc())
        )
        orms = session.execute(stmt).scalars().all()
        return [notification_orm_to_dataclass(orm) for orm in orms]


def get_oldest_pending_notification() -> Optional[PendingNotification]:
    """Get the oldest notification awaiting a rating."""
    with get_session() as session:
        stmt = (
            select(PendingNotificationORM)
            .where(PendingNotificationORM.rating_received == 0)
            .order_by(PendingNotificationORM.notified_at.asc())
            .limit(1)
        )
        orm = session.execute(stmt).scalar_one_or_none()
        if orm is None:
            return None
        return notification_orm_to_dataclass(orm)


def mark_notification_rated(notification_id: int):
    """Mark a notification as having received a rating."""
    with get_session() as session:
        orm = session.get(PendingNotificationORM, notification_id)
        if orm is not None:
            orm.rating_received = 1


def get_last_scan_time(source_type: SourceType) -> Optional[int]:
    """Get the last scan time for a source type."""
    with get_session() as session:
        orm = session.get(ScanHistoryORM, source_type.value)
        if orm is None:
            return None
        return orm.last_scan_epoch


def update_scan_history(source_type: SourceType, articles_found: int = 0, articles_interesting: int = 0):
    """Update the scan history for a source type."""
    with get_session() as session:
        orm = session.get(ScanHistoryORM, source_type.value)
        if orm is None:
            orm = ScanHistoryORM(
                source_type=source_type.value,
                last_scan_epoch=int(time.time()),
                articles_found=articles_found,
                articles_interesting=articles_interesting,
            )
            session.add(orm)
        else:
            orm.last_scan_epoch = int(time.time())
            orm.articles_found = articles_found
            orm.articles_interesting = articles_interesting
