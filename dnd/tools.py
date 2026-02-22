"""
DM tools for the D&D agent system.

Provides tools the Dungeon Master agent can call during its ReAct loop:
dice rolling, party status checks, damage/healing application, and
game history retrieval.
"""

import logging
import random
import re

from langchain_core.tools import tool

from dnd.database import (
    get_game_by_id,
    get_recent_events,
    update_player_hp,
    add_event,
)
from dnd.models import EventType

logger = logging.getLogger(__name__)

# Pattern for D&D dice notation: NdS+M or NdS-M or NdS
DICE_PATTERN = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$")


def _parse_and_roll(notation: str) -> tuple[list[int], int, int]:
    """Parse dice notation and roll. Returns (individual_rolls, modifier, total)."""
    notation = notation.strip().lower().replace(" ", "")
    match = DICE_PATTERN.match(notation)
    if not match:
        raise ValueError(
            f"Invalid dice notation '{notation}'. "
            "Use format like '1d20', '2d6+3', '1d8-1'."
        )

    num_dice = int(match.group(1))
    num_sides = int(match.group(2))
    modifier = int(match.group(3)) if match.group(3) else 0

    if num_dice < 1 or num_dice > 100:
        raise ValueError("Number of dice must be between 1 and 100.")
    if num_sides < 2 or num_sides > 100:
        raise ValueError("Number of sides must be between 2 and 100.")

    rolls = [random.randint(1, num_sides) for _ in range(num_dice)]
    total = sum(rolls) + modifier
    return rolls, modifier, total


class DMTools:
    """Tools for the Dungeon Master agent, bound to a specific game.

    Create one instance per agent invocation, call ``as_tools()`` to get
    the list of LangChain tool functions.
    """

    def __init__(self, game_id: int):
        self.game_id = game_id

    def as_tools(self):
        """Return LangChain tools bound to this game."""
        game_id = self.game_id

        @tool
        def roll_dice(notation: str) -> str:
            """Roll dice using D&D notation.

            Use this for skill checks, attack rolls, damage rolls, saving throws, etc.
            Common rolls:
            - 1d20 for skill checks and attack rolls
            - 1d20+3 for checks with a modifier
            - 2d6+2 for damage with a modifier
            - 1d4, 1d6, 1d8, 1d10, 1d12 for various damage dice

            Args:
                notation: Dice notation string, e.g. '1d20', '2d6+3', '1d8-1'
            """
            logger.info("roll_dice called with notation=%r", notation)
            try:
                rolls, modifier, total = _parse_and_roll(notation)
            except ValueError as e:
                return str(e)

            if modifier > 0:
                return f"Rolled {notation}: {rolls} + {modifier} = {total}"
            elif modifier < 0:
                return f"Rolled {notation}: {rolls} - {abs(modifier)} = {total}"
            else:
                return f"Rolled {notation}: {rolls} = {total}"

        @tool
        def get_party_status() -> str:
            """Get the current status of all players in the party.

            Returns each player's name, class, current HP, and max HP.
            Use this to check the party's condition before making decisions.
            """
            logger.info("get_party_status called for game_id=%d", game_id)
            game = get_game_by_id(game_id)
            if game is None:
                return "Error: game not found."

            if not game.players:
                return "No players in the party."

            lines = []
            for p in game.players:
                status = "DEAD" if p.hp <= 0 else f"{p.hp}/{p.max_hp} HP"
                lines.append(
                    f"- {p.character_name} ({p.character_class.value.title()}) "
                    f"[{status}] Level {p.level}"
                )
            return "Party status:\n" + "\n".join(lines)

        @tool
        def apply_damage(player_name: str, amount: int, reason: str) -> str:
            """Apply damage or healing to a player.

            Use negative amounts for damage, positive for healing.
            Always provide a reason so it's recorded in the game log.

            Args:
                player_name: The character name of the player to affect
                amount: HP change — negative for damage (e.g. -5), positive for healing (e.g. 3)
                reason: Brief description of why (e.g. 'goblin sword slash', 'healing spell')
            """
            logger.info(
                "apply_damage called: player=%r amount=%d reason=%r",
                player_name, amount, reason,
            )
            game = get_game_by_id(game_id)
            if game is None:
                return "Error: game not found."

            target = None
            for p in game.players:
                if p.character_name.lower() == player_name.lower():
                    target = p
                    break

            if target is None:
                names = [p.character_name for p in game.players]
                return (
                    f"No player named '{player_name}' found. "
                    f"Available players: {', '.join(names)}"
                )

            new_hp = max(0, min(target.max_hp, target.hp + amount))
            update_player_hp(target.id, new_hp)

            # Record as a game event
            if amount < 0:
                event_content = f"{target.character_name} takes {abs(amount)} damage ({reason}). HP: {target.hp} -> {new_hp}"
            else:
                event_content = f"{target.character_name} heals {amount} HP ({reason}). HP: {target.hp} -> {new_hp}"

            add_event(
                game_id=game_id,
                turn_number=game.turn_number,
                event_type=EventType.SYSTEM,
                content=event_content,
            )

            return event_content

        @tool
        def get_recent_history(limit: int = 20) -> str:
            """Get recent game events for context.

            Returns the most recent narrations, player actions, and resolutions.

            Args:
                limit: Maximum number of events to return (default 20)
            """
            logger.info("get_recent_history called for game_id=%d limit=%d", game_id, limit)
            events = get_recent_events(game_id, limit=limit)

            if not events:
                return "No events yet — this is the start of the adventure."

            lines = []
            for e in events:
                lines.append(f"[{e.event_type.value.upper()}] {e.content}")
            return "\n".join(lines)

        @tool
        def request_clarification(question: str) -> str:
            """Ask the player a clarifying question before resolving their action.

            Use this when the player's stated action is ambiguous and the ambiguity
            would meaningfully change the outcome. Examples:
            - "Which goblin do you want to attack - the one by the door or the one on the ledge?"
            - "Do you want to use a spell slot or try a regular attack?"
            - "Are you trying to sneak past or create a distraction?"

            Do NOT use this for simple actions that can be resolved directly.
            Only ask when genuine ambiguity would change the outcome.

            Args:
                question: The clarifying question to ask the player.
            """
            logger.info("request_clarification called: question=%r", question)
            return f"CLARIFICATION_REQUESTED: {question}"

        return [roll_dice, get_party_status, apply_damage, get_recent_history, request_clarification]
