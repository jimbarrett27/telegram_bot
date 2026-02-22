"""
Spell Checker sub-agent.

Validates spell casting against class spell lists, spell slots, components,
and the SRD spell database. The DM agent invokes this as a tool before
allowing any spell to be cast.
"""

import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool

from dnd.agent import Agent
from dnd.database import get_game_by_id, get_player_inventory, get_spell_slots
from dnd.srd_lookup import get_srd

logger = logging.getLogger(__name__)

SPELL_CHECKER_PROMPT = """\
You are a D&D 5e spell rules expert. Your job is to validate whether a player \
can cast a specific spell, and to provide the spell's mechanical details to the DM.

When asked to validate a spell cast, follow these steps:
1. Use lookup_spell to find the spell in the SRD and get its details (level, \
components, range, duration, damage)
2. Use get_class_spell_list to verify the caster's class can cast this spell
3. Use get_spell_slots to check if the caster has an available spell slot of \
the required level
4. If the spell requires material components (M), use get_player_inventory to \
check the caster has them (or an arcane focus/holy symbol)

Then return ONE of:
- VALID: The spell can be cast. Include the spell's key stats (level, range, \
damage/effect, save DC if any, duration) so the DM can resolve it properly. \
Also state which spell slot level will be consumed.
- INVALID: The spell CANNOT be cast. Explain why (e.g., "Wizards cannot cast \
Cure Wounds — it's a Cleric spell", "No remaining 2nd level spell slots", \
"Fireball requires a 3rd level slot but caster only has 1st level slots").

Notes:
- Cantrips (0-level spells) don't require spell slots
- A spell can be cast using a higher-level slot than required (upcasting)
- Warriors and Rogues cannot cast spells at all
- An Arcane Focus or Holy Symbol can substitute for material components \
(unless the component has a gold cost listed)

Keep responses concise — the DM needs a quick ruling with key spell stats.
"""


def create_spell_checker_tools(game_id: int):
    """Create the tools for the spell checker agent."""
    srd = get_srd()

    @tool
    def lookup_spell(name: str) -> str:
        """Look up a spell in the SRD.

        Returns the full spell description including level, casting time,
        range, components, duration, and effect.

        Args:
            name: Spell name (e.g. 'fireball', 'cure wounds', 'magic missile')
        """
        return srd.get_spell(name)

    @tool
    def get_class_spell_list(class_name: str) -> str:
        """Get the list of spells available to a character class.

        Args:
            class_name: Class name (e.g. 'cleric', 'mage', 'wizard')
        """
        return srd.get_class_spell_list(class_name)

    @tool
    def get_spell_slots_tool(player_name: str) -> str:
        """Check a player's remaining spell slots.

        Args:
            player_name: The character name to check
        """
        game = get_game_by_id(game_id)
        if game is None:
            return "Error: game not found."
        for p in game.players:
            if p.character_name.lower() == player_name.lower():
                if p.character_class.value in ("warrior", "rogue"):
                    return f"{p.character_name} is a {p.character_class.value.title()} and cannot cast spells."
                slots = get_spell_slots(p.id)
                if slots is None:
                    return f"{p.character_name} has no spell slots configured."
                lines = [f"Spell slots for {p.character_name} ({p.character_class.value.title()}):"]
                for lvl in range(1, 10):
                    current = getattr(slots, f"level_{lvl}")
                    maximum = getattr(slots, f"max_level_{lvl}")
                    if maximum > 0:
                        lines.append(f"  Level {lvl}: {current}/{maximum}")
                if len(lines) == 1:
                    lines.append("  No spell slots available.")
                return "\n".join(lines)
        return f"Player '{player_name}' not found."

    @tool
    def get_player_inventory_tool(player_name: str) -> str:
        """Check a player's inventory for spell components or a focus.

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

    return [lookup_spell, get_class_spell_list, get_spell_slots_tool, get_player_inventory_tool]


def create_spell_checker(game_id: int, llm: BaseChatModel) -> Agent:
    """Create a spell checker sub-agent for the given game.

    Args:
        game_id: The database ID of the game.
        llm: The LLM to use (typically a cheap/fast model).

    Returns:
        An Agent that can be wrapped with as_tool() for the DM agent.
    """
    tools = create_spell_checker_tools(game_id)
    return Agent(
        name="spell_checker",
        system_prompt=SPELL_CHECKER_PROMPT,
        tools=tools,
        llm=llm,
    )
