"""
Event summarization for DM memory persistence.

After each resolved action, summarizes recent events into a running
"story so far" narrative that stays in the DM's system prompt.
"""

import logging

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from dnd.database import get_recent_events, get_story_summary, update_story_summary
from gcp_util.secrets import get_gemini_api_key

logger = logging.getLogger(__name__)

SUMMARIZE_PROMPT = """\
You are a concise story summarizer for a D&D adventure.

Given the existing story summary and recent game events, write an updated summary \
of the adventure so far. Focus on:
- Plot developments and quest progress
- Important player decisions and their consequences
- NPC interactions and relationships
- Location changes and discoveries
- Combat outcomes and injuries

Keep the summary to 3-5 paragraphs maximum. Be specific about names, places, and outcomes. \
Write in past tense, third person.

## Existing Summary
{existing_summary}

## Recent Events
{recent_events}

Write the updated summary now:"""


def summarize_events(
    game_id: int,
    model_name: str = "gemini-2.5-flash",
) -> str:
    """Summarize recent events and update the game's story_summary.

    Reads the current story_summary + recent events, invokes a cheap LLM
    to produce an updated summary, and stores it back on the game.

    Args:
        game_id: The game to summarize.
        model_name: The Gemini model to use for summarization.

    Returns:
        The updated summary text.
    """
    existing_summary = get_story_summary(game_id)
    events = get_recent_events(game_id, limit=30)

    if not events:
        return existing_summary

    event_lines = []
    for e in events:
        event_lines.append(f"[{e.event_type.value.upper()}] {e.content}")
    recent_events_text = "\n".join(event_lines)

    prompt = SUMMARIZE_PROMPT.format(
        existing_summary=existing_summary or "(No previous summary — this is the beginning of the adventure.)",
        recent_events=recent_events_text,
    )

    api_key = get_gemini_api_key()
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
    )

    response = llm.invoke([HumanMessage(content=prompt)])
    summary = response.content.strip()

    update_story_summary(game_id, summary)
    logger.info("Updated story summary for game_id=%d (%d chars)", game_id, len(summary))

    return summary
