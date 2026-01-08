"""
LLM-based interest screening for articles.
"""

import json
from typing import Tuple

from content_screening.constants import PROMPTS_DIR
from content_screening.models import Article
from llm.llm_util import get_llm_response
from util.logging_util import setup_logger

logger = setup_logger(__name__)

SCREEN_ARTICLE_TEMPLATE = PROMPTS_DIR / "screen_article.jinja2"


def screen_article(article: Article) -> Tuple[bool, float, str]:
    """
    Screen an article using LLM to determine if it's relevant to pharmacovigilance.

    Args:
        article: The article to screen.

    Returns:
        Tuple of (is_relevant, confidence 0.0-1.0, reasoning string).
    """
    try:
        response = get_llm_response(
            str(SCREEN_ARTICLE_TEMPLATE),
            {
                "title": article.title,
                "abstract": article.abstract or "",
            }
        )

        # Parse JSON response - handle potential markdown code blocks
        response = response.strip()
        if response.startswith("```"):
            # Remove markdown code block
            lines = response.split("\n")
            response = "\n".join(lines[1:-1])

        result = json.loads(response)

        is_relevant = result.get("is_relevant", False)
        confidence = float(result.get("confidence", 0.0))
        reasoning = result.get("reasoning", "No reasoning provided")

        logger.info(f"Screened '{article.title[:50]}...': relevant={is_relevant}, confidence={confidence:.2f}")
        return is_relevant, confidence, reasoning

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"Response was: {response}")
        # Default to not relevant on parse error
        return False, 0.0, f"Failed to parse LLM response: {e}"
    except Exception as e:
        logger.error(f"Error screening article: {e}")
        # Default to relevant on error to avoid missing papers
        return True, 0.5, f"Error during screening: {e}"


def screen_and_update_article(article: Article) -> Article:
    """
    Screen an article and update it with the LLM's assessment.

    Args:
        article: The article to screen.

    Returns:
        The article with llm_interest_score and llm_reasoning set.
    """
    is_relevant, confidence, reasoning = screen_article(article)
    article.llm_interest_score = confidence if is_relevant else 0.0
    article.llm_reasoning = reasoning
    return article
