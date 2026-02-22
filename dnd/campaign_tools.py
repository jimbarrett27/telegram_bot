"""Campaign lookup tools for the DM agent.

Provides tools to search and retrieve parsed adventure sections
from the database during gameplay.
"""

from langchain_core.tools import tool as tool_decorator

from dnd.database import get_campaign_sections, search_campaign_sections


class CampaignTools:
    """Tools for looking up adventure content during play."""

    def __init__(self, game_id: int):
        self.game_id = game_id

    def as_tools(self) -> list:
        """Return LangChain tool functions for campaign lookup."""
        game_id = self.game_id

        @tool_decorator
        def lookup_campaign(query: str) -> str:
            """Search the adventure document for information about a topic.

            Use this to look up details about locations, NPCs, encounters,
            items, or any other adventure content. Pass a keyword or phrase
            to search for (e.g. "ogre", "statue", "Larry", "Scene 3").

            Args:
                query: A keyword or phrase to search for in the adventure.
            """
            sections = search_campaign_sections(game_id, query)
            if not sections:
                return f"No adventure content found matching '{query}'."

            results = []
            for s in sections[:3]:  # Limit to top 3 matches
                results.append(f"## {s.section_title}\n{s.section_content}")
            return "\n\n---\n\n".join(results)

        @tool_decorator
        def list_campaign_sections() -> str:
            """List all section titles in the current adventure.

            Use this to see what sections are available to look up.
            Helpful when you need to find the right section name to query.
            """
            sections = get_campaign_sections(game_id)
            if not sections:
                return "No adventure sections loaded."

            lines = [f"{i+1}. {s.section_title}" for i, s in enumerate(sections)]
            return "\n".join(lines)

        return [lookup_campaign, list_campaign_sections]
