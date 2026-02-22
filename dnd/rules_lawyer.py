"""
Rules Lawyer sub-agent.

Validates player actions against inventory, attributes, and SRD rules.
The DM agent invokes this as a tool before resolving physical actions.
"""

import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool

from dnd.agent import Agent
from dnd.database import get_game_by_id, get_player_inventory, get_player_attributes
from dnd.srd_lookup import get_srd

logger = logging.getLogger(__name__)

RULES_LAWYER_PROMPT = """\
You are a D&D 5e rules expert (the "Rules Lawyer"). Your job is to validate \
whether a player's proposed action is allowed given their character's inventory, \
attributes, and the D&D rules.

When asked to validate an action, follow these steps:
1. Use get_player_inventory to check what items the player actually has
2. Use get_player_attributes to check their ability scores
3. Use lookup_equipment if the action involves a weapon or armor — verify stats
4. Use lookup_rules if the action involves a specific game mechanic (grapple, shove, etc.)

Then return ONE of:
- VALID: The action is allowed. Briefly explain why.
- INVALID: The action is NOT allowed. Explain why (e.g., "Aragorn doesn't have a spear \
in their inventory", "Warriors cannot cast spells").
- CONDITIONAL: The action requires a check. Specify what kind (e.g., "Requires a DC 13 \
Strength (Athletics) check to grapple").

Be strict but fair. If a player tries to use an item they don't have, that's INVALID. \
If they try something creative but plausible, that's CONDITIONAL with an appropriate check.

Keep your responses concise — the DM agent needs a quick ruling, not a lecture.
"""


def create_rules_lawyer_tools(game_id: int):
    """Create the tools for the rules lawyer agent."""
    srd = get_srd()

    @tool
    def get_player_inventory_tool(player_name: str) -> str:
        """Check what items a player has in their inventory.

        Args:
            player_name: The character name to check
        """
        game = get_game_by_id(game_id)
        if game is None:
            return "Error: game not found."
        for p in game.players:
            if p.character_name.lower() == player_name.lower():
                items = get_player_inventory(p.id)
                if not items:
                    return f"{p.character_name} has no items."
                lines = [f"Inventory for {p.character_name}:"]
                for item in items:
                    equipped = " [EQUIPPED]" if item.equipped else ""
                    qty = f" x{item.quantity}" if item.quantity > 1 else ""
                    lines.append(f"  - {item.item_name}{qty} ({item.item_type}){equipped}")
                return "\n".join(lines)
        return f"Player '{player_name}' not found."

    @tool
    def get_player_attributes_tool(player_name: str) -> str:
        """Check a player's ability scores (STR, DEX, CON, INT, WIS, CHA).

        Args:
            player_name: The character name to check
        """
        game = get_game_by_id(game_id)
        if game is None:
            return "Error: game not found."
        for p in game.players:
            if p.character_name.lower() == player_name.lower():
                attrs = get_player_attributes(p.id)
                if attrs is None:
                    return f"No attributes found for {p.character_name}."
                lines = [f"Attributes for {p.character_name} ({p.character_class.value.title()}):"]
                for attr, val in attrs.items():
                    mod = (val - 10) // 2
                    sign = "+" if mod >= 0 else ""
                    lines.append(f"  {attr.upper()[:3]}: {val} ({sign}{mod})")
                return "\n".join(lines)
        return f"Player '{player_name}' not found."

    @tool
    def lookup_equipment(name: str) -> str:
        """Look up a weapon or armor in the SRD rules.

        Returns stats like damage, AC, weight, properties.

        Args:
            name: Equipment name (e.g. 'longsword', 'chain mail')
        """
        return srd.get_equipment(name)

    @tool
    def lookup_rules(topic: str) -> str:
        """Look up a D&D combat or mechanics rule.

        Args:
            topic: The rule topic (e.g. 'grapple', 'opportunity attack', 'cover', 'stealth')
        """
        return srd.lookup_rule(topic)

    return [get_player_inventory_tool, get_player_attributes_tool, lookup_equipment, lookup_rules]


def create_rules_lawyer(game_id: int, llm: BaseChatModel) -> Agent:
    """Create a rules lawyer sub-agent for the given game.

    Args:
        game_id: The database ID of the game.
        llm: The LLM to use (typically a cheap/fast model).

    Returns:
        An Agent that can be wrapped with as_tool() for the DM agent.
    """
    tools = create_rules_lawyer_tools(game_id)
    return Agent(
        name="rules_lawyer",
        system_prompt=RULES_LAWYER_PROMPT,
        tools=tools,
        llm=llm,
    )
