"""
DM memory tools for note-taking during adventures.

Provides write_note and read_notes tools that allow the DM agent to
persist important facts across turns.
"""

import logging

from langchain_core.tools import tool

from dnd.database import add_dm_note, get_dm_notes

logger = logging.getLogger(__name__)


class MemoryTools:
    """Tools for DM note-taking, bound to a specific game."""

    def __init__(self, game_id: int):
        self.game_id = game_id

    def as_tools(self):
        """Return LangChain tools bound to this game."""
        game_id = self.game_id

        @tool
        def write_note(note: str) -> str:
            """Record an important fact or observation for future reference.

            Use this to remember key details you'll need later:
            - NPC names, attitudes, and relationships
            - Plot decisions the players made
            - Items given, received, or destroyed
            - Location descriptions and changes
            - Quest objectives and progress
            - Any other facts you might forget

            Write notes AFTER resolving an action, not before.
            Keep notes concise but specific.

            Args:
                note: The fact or observation to record.
            """
            logger.info("write_note called for game_id=%d: %s", game_id, note[:80])
            dm_note = add_dm_note(game_id, note)
            return f"Note recorded (#{dm_note.id})."

        @tool
        def read_notes() -> str:
            """Retrieve all stored DM notes for this game.

            Use this to refresh your memory about important facts
            you've previously recorded.
            """
            logger.info("read_notes called for game_id=%d", game_id)
            notes = get_dm_notes(game_id)
            if not notes:
                return "No notes recorded yet."
            lines = []
            for n in notes:
                lines.append(f"- {n.content}")
            return "DM Notes:\n" + "\n".join(lines)

        return [write_note, read_notes]
