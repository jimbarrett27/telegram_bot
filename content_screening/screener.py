"""
LLM-based interest screening for articles.

This module is a placeholder for future LLM-based screening functionality.
"""

from typing import Optional, Tuple

from content_screening.constants import PROMPTS_DIR
from content_screening.models import Article
from util.logging_util import setup_logger

logger = setup_logger(__name__)

SCREEN_ARTICLE_TEMPLATE = PROMPTS_DIR / "screen_article.jinja2"


def screen_article(article: Article, user_interests: str) -> Tuple[float, str]:
    """
    Screen an article using LLM to determine interest level.

    Args:
        article: The article to screen.
        user_interests: Description of the user's interests.

    Returns:
        Tuple of (interest_score 0.0-1.0, reasoning string).
    """
    # TODO: Implement LLM-based screening using get_llm_response
    # from llm.llm_util import get_llm_response
    #
    # response = get_llm_response(
    #     str(SCREEN_ARTICLE_TEMPLATE),
    #     {
    #         "title": article.title,
    #         "abstract": article.abstract,
    #         "categories": article.categories,
    #         "user_interests": user_interests,
    #     }
    # )
    # Parse JSON response and return score and reasoning

    logger.warning("LLM screening not yet implemented, returning default score")
    return 0.5, "LLM screening not yet implemented"


def update_article_with_screening(article: Article, user_interests: str) -> Article:
    """
    Screen an article and update it with the LLM's assessment.

    Args:
        article: The article to screen.
        user_interests: Description of the user's interests.

    Returns:
        The article with llm_interest_score and llm_reasoning set.
    """
    score, reasoning = screen_article(article, user_interests)
    article.llm_interest_score = score
    article.llm_reasoning = reasoning
    return article
