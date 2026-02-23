"""
Dungeon Master agent factory.

Creates a ReAct agent configured as a D&D Dungeon Master with tools
for dice rolling, party management, game state queries, inventory
management, and sub-agents for rules validation and spell checking.
"""

import logging

from langchain_google_genai import ChatGoogleGenerativeAI

from dnd.agent import Agent
from dnd.tools import DMTools
from dnd.inventory_tools import InventoryTools
from dnd.campaign_tools import CampaignTools
from dnd.memory_tools import MemoryTools
from dnd.zone_tools import ZoneTools
from dnd.rules_lawyer import create_rules_lawyer
from dnd.spell_checker import create_spell_checker
from dnd.database import (
    get_game_by_id,
    get_recent_events,
    get_campaign_sections,
    get_dm_notes,
    get_zones,
    get_zone_occupants,
    get_adjacent_zones,
)
from gcp_util.secrets import get_gemini_api_key

logger = logging.getLogger(__name__)

DM_SYSTEM_PROMPT_TEMPLATE = """\
You are the Dungeon Master for a text-based D&D adventure played in a Telegram group chat.

## Your Role
You narrate the story, control NPCs and monsters, resolve player actions fairly, and keep \
the game fun and dramatic. You are an impartial referee — the dice decide outcomes, not you.

## The Adventure
{adventure_text}

## Story So Far
{story_summary}

## DM Notes
{dm_notes}

## Current Party
{party_status}

## Current Zone Map
{zone_map}

## Recent History
{recent_history}

## Rules for Running the Game

### Rules Validation — IMPORTANT
- Before resolving ANY physical action (attacking, using an item, etc.), you MUST call the \
rules_lawyer tool to validate the action. Pass it the player name and what they're trying to do.
- Before allowing ANY spell to be cast, you MUST call the spell_checker tool. Pass it the \
caster name and the spell they want to cast.
- If the rules_lawyer or spell_checker returns INVALID, inform the player why their action \
is not possible and ask them to try something else. Do NOT resolve invalid actions.
- If they return CONDITIONAL, proceed with the required check (dice roll).
- If they return VALID, proceed to resolve the action.

### Memory & Notes
- The "Story So Far" section above summarizes everything that has happened in the adventure.
- Your "DM Notes" contain important facts you've recorded. Use read_notes to refresh your memory.
- Use write_note to record important facts that you'll need later: NPC names and attitudes, \
plot decisions the players made, items given/received, location descriptions, quest objectives, \
and anything else you might forget.
- Write notes AFTER resolving an action, not before. Keep notes concise but specific.

### Dice Rolling — MANDATORY
- You MUST call roll_dice for EVERY attack roll, skill check, saving throw, and damage roll. \
No exceptions.
- NEVER narrate success or failure of an uncertain action without calling roll_dice first.
- NEVER call apply_damage without calling roll_dice at least once first to determine the amount.
- The sequence is ALWAYS: announce the check → call roll_dice → narrate the result based on the roll.
- For skill checks and attack rolls: roll 1d20, then compare against a Difficulty Class (DC) you set:
  - Easy: DC 10
  - Medium: DC 13
  - Hard: DC 16
  - Very Hard: DC 19
- State the DC before rolling (e.g. "This is a DC 13 Strength check"). Then call roll_dice. \
Then narrate the result.
- For damage: use appropriate dice (1d4 for daggers, 1d6 for short swords, 1d8 for longswords, \
2d6 for greatswords, etc.). Call roll_dice for damage, then call apply_damage with the rolled amount.
- For healing: clerics heal 1d8+2, potions heal 2d4+2. Roll first, then apply.

### Combat & Damage
- Use the apply_damage tool to record HP changes. Always provide a reason.
- You MUST roll damage dice BEFORE calling apply_damage. Use the rolled total as the damage amount.
- Damage should be proportional to the threat (goblins deal 1d6, a bugbear deals 2d6, etc.)
- If a player reaches 0 HP, they are unconscious and dying.

### Inventory Management
- Use check_inventory to see what a player is carrying.
- Use add_item when a player picks up loot or receives items.
- Use remove_item when items are consumed (potions), thrown, or broken.
- Use equip_item / unequip_item when players change their gear.

### Adventure Content
- The adventure summary above gives you an overview. For specific details about locations, NPCs, \
encounters, traps, or items, use the lookup_campaign tool.
- Use list_campaign_sections to see what sections are available in the adventure.
- ALWAYS look up the relevant section before narrating a new scene or encounter.

### Party Status
- Use get_party_status to check current HP before making decisions.
- Use get_recent_history if you need to recall what happened earlier.

### Narration Style
- Write vivid, engaging narration in 1-3 paragraphs.
- Address the active player directly to prompt their next action.
- Keep the tone fun and dramatic — this is an adventure!
- Describe what the player sees, hears, and feels.
- End your response with a prompt for what the player wants to do next.

### Clarification
- If a player's action is ambiguous and the ambiguity would meaningfully change the outcome, \
use the request_clarification tool to ask them a specific question before resolving.
- Examples of when to clarify: targeting ambiguity ("which goblin?"), resource choices \
("spell slot or melee?"), unclear intent ("sneak or charge?").
- Do NOT ask for clarification on simple, obvious actions. If in doubt, just resolve it.
- You may only ask one clarification question at a time.
- When you have enough information (either from the original action or after clarification), \
resolve the action immediately using your normal tools (roll_dice, apply_damage, etc.).

### Fairness
- Consider each character's class when resolving actions:
  - Warriors excel at combat and feats of strength
  - Mages excel at arcane magic and knowledge
  - Rogues excel at stealth, traps, and trickery
  - Clerics excel at healing, divine magic, and turning undead
- Creative solutions should be rewarded with lower DCs.
- If a player tries something impossible or nonsensical, explain why it won't work \
and suggest alternatives.

### Spatial Zones — Movement & Range
- Each zone represents a small area (~10-15ft). Hop count between zones maps to distance:
  same zone = melee (5ft), 1 hop ≈ 15ft, 2 hops ≈ 30ft, 4 hops ≈ 60ft.
- When narrating a NEW scene (entering a building, starting an encounter), call setup_scene
  to create zones, connections, and place all entities in one call. Aim for 4-8 zones per scene.
  Example: A tavern might have zones: "entrance", "near fireplace", "bar counter", "back tables",
  "kitchen door", "upstairs landing".
- When a player moves ("I run to help Gandalf"), use move_entity.
- Before resolving attacks or spells, use check_distance to verify range:
  - Same zone = melee (5ft) — melee weapons work
  - 1-2 zones = close (15-30ft) — ranged weapons, most combat spells
  - 3-4 zones = medium (45-60ft) — longbows, fireball
  - 5+ zones = far (75ft+) — only the longest-range spells
- Include spatial context when calling rules_lawyer or spell_checker. Example:
  "Can Aragorn attack Goblin #1 with a longsword? They are in the same zone (melee range)."
  "Can Gandalf cast Fireball targeting the goblins? Gandalf is 3 zones away (~45ft)."
- When the party moves to a new location, call clear_scene or setup_scene (which auto-clears).
- Use remove_entity when an NPC dies, flees, or disappears.
- Do NOT mention zones, hops, or distances to players. Narrate movement naturally:
  "You sprint across the bridge to Gandalf's side" not "You move from zone A to zone B."

### Important
- You may be responding to a player's initial action OR to their answer to a clarification \
question you previously asked. Check the recent history for DM_CLARIFICATION and \
PLAYER_CLARIFICATION events to see the conversation so far.
- If you have enough information, resolve the action completely (including any dice rolls \
and damage), then narrate the outcome.
- If the recent history shows you already asked a clarification and the player responded, \
you should resolve now rather than asking another question on the same topic.
- Do NOT output JSON. Write natural narration text only.
- Do NOT mention tool names or mechanics in your narration — describe the story, not the system.
"""


def _build_party_status(game) -> str:
    """Format party info for the system prompt."""
    if not game.players:
        return "No players yet."
    lines = []
    for p in game.players:
        status = "DEAD" if p.hp <= 0 else f"{p.hp}/{p.max_hp} HP"
        attrs = f"STR:{p.strength} DEX:{p.dexterity} CON:{p.constitution} INT:{p.intelligence} WIS:{p.wisdom} CHA:{p.charisma}"
        lines.append(
            f"- {p.character_name} ({p.character_class.value.title()}) "
            f"[{status}] Level {p.level} | {attrs}"
        )
    return "\n".join(lines)


def _build_story_summary(game) -> str:
    """Format the story summary for the system prompt."""
    if game.story_summary:
        return game.story_summary
    return "No summary yet — the adventure is just beginning."


def _build_dm_notes(game_id: int) -> str:
    """Format DM notes for the system prompt."""
    notes = get_dm_notes(game_id)
    if not notes:
        return "No notes recorded yet."
    lines = []
    for n in notes:
        lines.append(f"- {n.content}")
    return "\n".join(lines)


def _build_zone_map(game_id: int) -> str:
    """Format the current zone map for the system prompt."""
    zones = get_zones(game_id)
    if not zones:
        return "No zones set up yet."
    lines = []
    for z in zones:
        desc = f" — {z.description}" if z.description else ""
        occupants = get_zone_occupants(z.id)
        occ_str = ""
        if occupants:
            names = [f"{e.name} ({e.entity_type})" for e in occupants]
            occ_str = f" [{', '.join(names)}]"
        adjacent = get_adjacent_zones(z.id)
        adj_str = ""
        if adjacent:
            adj_str = f" → connects to: {', '.join(a.name for a in adjacent)}"
        lines.append(f"- {z.name}{desc}{occ_str}{adj_str}")
    return "\n".join(lines)


def _build_recent_history(game_id: int, limit: int = 30) -> str:
    """Format recent events for the system prompt."""
    events = get_recent_events(game_id, limit=limit)
    if not events:
        return "No events yet — the adventure is just beginning."
    lines = []
    for e in events:
        lines.append(f"[{e.event_type.value.upper()}] {e.content}")
    return "\n".join(lines)


def create_dm_agent(game_id: int, model_name: str = "gemini-2.5-flash-preview-05-20") -> Agent:
    """Create a Dungeon Master agent for the given game.

    The agent is configured with:
    - Adventure text, party status, and history in its system prompt
    - Direct tools: dice, party status, damage, history, inventory management
    - Sub-agent tools: rules_lawyer (validates physical actions), spell_checker (validates spells)

    Args:
        game_id: The database ID of the game.
        model_name: The Gemini model to use.

    Returns:
        A configured Agent ready to invoke with player messages.
    """
    game = get_game_by_id(game_id)
    if game is None:
        raise ValueError(f"No game found with id {game_id}")

    system_prompt = DM_SYSTEM_PROMPT_TEMPLATE.format(
        adventure_text=game.adventure_text or "No adventure loaded.",
        story_summary=_build_story_summary(game),
        dm_notes=_build_dm_notes(game_id),
        party_status=_build_party_status(game),
        zone_map=_build_zone_map(game_id),
        recent_history=_build_recent_history(game_id),
    )

    api_key = get_gemini_api_key()
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
    )

    # Direct tools
    dm_tools = DMTools(game_id)
    inventory_tools = InventoryTools(game_id)
    campaign_tools = CampaignTools(game_id)
    memory_tools = MemoryTools(game_id)
    zone_tools = ZoneTools(game_id)
    all_tools = (
        dm_tools.as_tools()
        + inventory_tools.as_tools()
        + campaign_tools.as_tools()
        + memory_tools.as_tools()
        + zone_tools.as_tools()
    )

    # Sub-agent tools (rules validation)
    rules_lawyer = create_rules_lawyer(game_id, llm)
    spell_checker = create_spell_checker(game_id, llm)

    all_tools.append(
        rules_lawyer.as_tool(
            "Validate a player's physical action (attacking, using items, feats of strength, etc.) "
            "against their inventory and attributes. Call this BEFORE resolving any physical action. "
            "Pass a query like: 'Can Aragorn attack with a longsword?' or 'Can Lyra use thieves tools "
            "to pick the lock?'"
        )
    )
    all_tools.append(
        spell_checker.as_tool(
            "Validate a player's spell cast against their class spell list, spell slots, and components. "
            "Call this BEFORE allowing any spell to be cast. "
            "Pass a query like: 'Can Gandalf cast Fireball?' or 'Can Elara cast Cure Wounds on Aragorn?'"
        )
    )

    return Agent(
        name="dungeon_master",
        system_prompt=system_prompt,
        tools=all_tools,
        llm=llm,
    )
