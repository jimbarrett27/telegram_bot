"""
Database operations for the content screening system.

Uses SQLAlchemy ORM for database access. The public API uses dataclass models
from models.py, with conversion to/from ORM models handled internally.
"""

import html
import re
import time
from typing import List, Optional, Tuple

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


# --- Cross-source deduplication ---------------------------------------------
#
# The unique constraint (source_type, external_id) only stops re-inserting the
# SAME paper from the SAME source. The same paper arriving from arXiv, a journal
# RSS feed and OpenAlex gets three different external_ids, so we dedup on a
# source-independent identity: DOI first (robust), normalized title as fallback
# (the only reliable arXiv<->OpenAlex bridge).

_TITLE_PUNCT_RE = re.compile(r"[^a-z0-9]+")


def normalize_doi(doi: Optional[str]) -> Optional[str]:
    """Normalize a DOI to a bare lowercase identifier (no URL prefix)."""
    if not doi:
        return None
    doi = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
            break
    return doi or None


def normalize_title(title: Optional[str]) -> Optional[str]:
    """Normalize a title for fuzzy identity: decode HTML entities, lowercase,
    collapse all non-alphanumeric runs to single spaces."""
    if not title:
        return None
    text = html.unescape(title)
    # Drop HTML tags that sometimes survive in feed titles (e.g. <em>...</em>).
    text = re.sub(r"<[^>]+>", "", text)
    text = _TITLE_PUNCT_RE.sub(" ", text.lower()).strip()
    return text or None


def load_dedup_index() -> Tuple[set, set]:
    """Load existing articles' normalized DOIs and titles into in-memory sets.

    Returns ``(doi_set, title_set)``. A few thousand rows is trivial to hold in
    memory; this is built once per scan and consulted before each insert.
    """
    doi_set: set = set()
    title_set: set = set()
    with get_session() as session:
        rows = session.execute(select(ArticleORM.doi, ArticleORM.title)).all()
    for doi, title in rows:
        nd = normalize_doi(doi)
        if nd:
            doi_set.add(nd)
        nt = normalize_title(title)
        if nt:
            title_set.add(nt)
    return doi_set, title_set


def is_duplicate(article: Article, doi_set: set, title_set: set) -> bool:
    """Whether ``article`` matches something already in the dedup index by DOI
    (primary) or normalized title (fallback)."""
    nd = normalize_doi(article.doi)
    if nd and nd in doi_set:
        return True
    nt = normalize_title(article.title)
    if nt and nt in title_set:
        return True
    return False


def add_to_dedup_index(article: Article, doi_set: set, title_set: set) -> None:
    """Record an article's identity keys so later candidates in the same run
    dedup against it (cross-source within a run)."""
    nd = normalize_doi(article.doi)
    if nd:
        doi_set.add(nd)
    nt = normalize_title(article.title)
    if nt:
        title_set.add(nt)


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
