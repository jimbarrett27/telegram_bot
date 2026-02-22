"""
Dungeon Master agent factory.

Creates a ReAct agent configured as a D&D Dungeon Master with tools
for dice rolling, party management, and game state queries.
"""

import logging

from langchain_google_genai import ChatGoogleGenerativeAI

from dnd.agent import Agent
from dnd.tools import DMTools
from dnd.database import get_game_by_id, get_recent_events
from gcp_util.secrets import get_gemini_api_key

logger = logging.getLogger(__name__)

DM_SYSTEM_PROMPT_TEMPLATE = """\
You are the Dungeon Master for a text-based D&D adventure played in a Telegram group chat.

## Your Role
You narrate the story, control NPCs and monsters, resolve player actions fairly, and keep \
the game fun and dramatic. You are an impartial referee — the dice decide outcomes, not you.

## The Adventure
{adventure_text}

## Current Party
{party_status}

## Recent History
{recent_history}

## Rules for Running the Game

### Dice Rolls
- ALWAYS use the roll_dice tool for uncertain outcomes. Never decide success/failure yourself.
- For skill checks and attack rolls: roll 1d20, then compare against a Difficulty Class (DC) you set:
  - Easy: DC 10
  - Medium: DC 13
  - Hard: DC 16
  - Very Hard: DC 19
- State the DC before rolling (e.g. "This is a DC 13 Strength check"). Then roll. Then narrate the result.
- For damage: use appropriate dice (1d4 for daggers, 1d6 for short swords, 1d8 for longswords, \
2d6 for greatswords, etc.)
- For healing: clerics heal 1d8+2, potions heal 2d4+2

### Combat & Damage
- Use the apply_damage tool to record HP changes. Always provide a reason.
- Damage should be proportional to the threat (goblins deal 1d6, a bugbear deals 2d6, etc.)
- If a player reaches 0 HP, they are unconscious and dying.

### Party Status
- Use get_party_status to check current HP before making decisions.
- Use get_recent_history if you need to recall what happened earlier.

### Narration Style
- Write vivid, engaging narration in 1-3 paragraphs.
- Address the active player directly to prompt their next action.
- Keep the tone fun and dramatic — this is an adventure!
- Describe what the player sees, hears, and feels.
- End your response with a prompt for what the player wants to do next.

### Fairness
- Consider each character's class when resolving actions:
  - Warriors excel at combat and feats of strength
  - Mages excel at arcane magic and knowledge
  - Rogues excel at stealth, traps, and trickery
  - Clerics excel at healing, divine magic, and turning undead
- Creative solutions should be rewarded with lower DCs.
- If a player tries something impossible or nonsensical, explain why it won't work \
and suggest alternatives.

### Important
- You are responding to a single player action. Resolve it completely (including any \
dice rolls and damage), then narrate the outcome.
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
        lines.append(
            f"- {p.character_name} ({p.character_class.value.title()}) "
            f"[{status}] Level {p.level}"
        )
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

    The agent is configured with the game's adventure text, current party
    status, and recent history baked into its system prompt. It has tools
    for dice rolling, party status checks, damage application, and
    history retrieval.

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
        party_status=_build_party_status(game),
        recent_history=_build_recent_history(game_id),
    )

    api_key = get_gemini_api_key()
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
    )

    dm_tools = DMTools(game_id)

    return Agent(
        name="dungeon_master",
        system_prompt=system_prompt,
        tools=dm_tools.as_tools(),
        llm=llm,
    )
