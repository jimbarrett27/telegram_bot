"""
Data models for the content screening system.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List


class SourceType(Enum):
    ARXIV = "arxiv"
    BLOG = "blog"
    NEWSLETTER = "newsletter"
    RSS = "rss"


@dataclass
class Article:
    """Unified article representation for all content sources."""
    external_id: str
    source_type: SourceType
    title: str
    url: str
    id: Optional[int] = None
    abstract: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    keywords_matched: List[str] = field(default_factory=list)
    discovered_at: int = 0
    llm_interest_score: Optional[float] = None
    llm_reasoning: Optional[str] = None
    llm_tags: List[str] = field(default_factory=list)
    embedding: Optional[bytes] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ArticleRating:
    """User rating for an article."""
    article_id: int
    rating: int
    rated_at: int
    id: Optional[int] = None


@dataclass
class PendingNotification:
    """Tracks article notifications awaiting user rating."""
    article_id: int
    notified_at: int
    id: Optional[int] = None
    rating_received: bool = False
