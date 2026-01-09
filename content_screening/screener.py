"""
LLM-based interest screening for articles.
"""

import json
from typing import List, Tuple

from content_screening.constants import PROMPTS_DIR
from content_screening.models import Article
from llm.llm_util import get_llm_response
from util.logging_util import setup_logger

logger = setup_logger(__name__)

SCREEN_ARTICLE_TEMPLATE = PROMPTS_DIR / "screen_article.jinja2"

# Mapping from categorical relevance/confidence to numeric scores
RELEVANCE_SCORES = {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.0}
CONFIDENCE_SCORES = {"HIGH": 1.0, "MEDIUM": 0.6, "LOW": 0.3}


def screen_article(article: Article) -> Tuple[bool, float, str, List[str]]:
    """
    Screen an article using LLM to determine if it's relevant to pharmacovigilance.

    Args:
        article: The article to screen.

    Returns:
        Tuple of (is_relevant, score 0.0-1.0, reasoning string, tags list).
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

        relevance = result.get("relevance", "LOW").upper()
        confidence = result.get("confidence", "LOW").upper()
        reasoning = result.get("reasoning", "No reasoning provided")
        tags = result.get("tags", [])

        # Convert categorical values to numeric score
        relevance_score = RELEVANCE_SCORES.get(relevance, 0.0)
        confidence_score = CONFIDENCE_SCORES.get(confidence, 0.3)

        # Combined score: relevance weighted by confidence
        score = relevance_score * confidence_score
        is_relevant = relevance in ("HIGH", "MEDIUM")

        logger.info(f"Screened '{article.title[:50]}...': relevance={relevance}, confidence={confidence}, score={score:.2f}")
        return is_relevant, score, reasoning, tags

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"Response was: {response}")
        # Default to not relevant on parse error
        return False, 0.0, f"Failed to parse LLM response: {e}", []
    except Exception as e:
        logger.error(f"Error screening article: {e}")
        # Default to relevant on error to avoid missing papers
        return True, 0.5, f"Error during screening: {e}", []


def screen_and_update_article(article: Article) -> Article:
    """
    Screen an article and update it with the LLM's assessment.

    Args:
        article: The article to screen.

    Returns:
        The article with llm_interest_score, llm_reasoning, and llm_tags set.
    """
    is_relevant, score, reasoning, tags = screen_article(article)
    article.llm_interest_score = score if is_relevant else 0.0
    article.llm_reasoning = reasoning
    article.llm_tags = tags
    return article
