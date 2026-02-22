"""
AI player agent for auto-playing turns.

Used for:
1. AFK timeout — when a human player hasn't acted in 24 hours
2. AI party members — characters added via /dnd_add_ai that always auto-play
"""

import asyncio
import logging

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from dnd.database import (
    get_game_by_id,
    get_player_by_id,
    get_player_inventory,
    get_recent_events,
    add_event,
)
from dnd.models import EventType
from dnd.game_logic import (
    get_active_player,
    start_player_action,
    continue_player_action,
    finalize_action,
)
from gcp_util.secrets import get_gemini_api_key

logger = logging.getLogger(__name__)

AI_PLAYER_PROMPT_TEMPLATE = """\
You are {character_name}, a {character_class} in a D&D adventure played in a group chat.

## Your Character
Class: {character_class}
HP: {hp}/{max_hp}
Attributes: STR:{strength} DEX:{dexterity} CON:{constitution} \
INT:{intelligence} WIS:{wisdom} CHA:{charisma}

## Your Inventory
{inventory}

## Story So Far
{story_summary}

## Recent History
{recent_history}

## Party Status
{party_status}

## Instructions
Decide what to do on your turn. Consider:
- Your class strengths (warriors fight, mages cast, rogues sneak, clerics heal/protect)
- The current situation from recent history
- Your inventory and available equipment
- The party's needs (if someone is low HP, a cleric should heal)
- Be cooperative — support the party's goals

Respond with ONLY your action in first person, 1-2 sentences.
Example: "I cast Cure Wounds on Alara to heal her injuries."
Example: "I draw my longsword and attack the goblin blocking the door."
"""

AI_CLARIFICATION_PROMPT = """\
The Dungeon Master asks you: "{question}"

Respond in character as {character_name} the {character_class}. \
Answer the question directly in 1 sentence.
"""


def generate_ai_action(
    game_id: int,
    player_id: int,
    model_name: str = "gemini-2.5-flash-preview-05-20",
) -> str:
    """Generate an action for an AI-controlled player.

    Creates a lightweight LLM call that considers the character's class,
    inventory, recent history, and party status to pick a sensible action.

    Returns:
        An action string like "I attack the nearest goblin with my longsword."
    """
    game = get_game_by_id(game_id)
    player = get_player_by_id(player_id)
    if game is None or player is None:
        return "I look around cautiously."

    # Build inventory text
    items = get_player_inventory(player_id)
    if items:
        inv_lines = []
        for item in items:
            equipped = " [equipped]" if item.equipped else ""
            qty = f" x{item.quantity}" if item.quantity > 1 else ""
            inv_lines.append(f"- {item.item_name}{qty}{equipped}")
        inventory_text = "\n".join(inv_lines)
    else:
        inventory_text = "No items."

    # Build recent history
    events = get_recent_events(game_id, limit=15)
    if events:
        history_lines = [f"[{e.event_type.value.upper()}] {e.content}" for e in events]
        recent_history = "\n".join(history_lines)
    else:
        recent_history = "The adventure is just beginning."

    # Build party status
    party_lines = []
    for p in game.players:
        status = "DEAD" if p.hp <= 0 else f"{p.hp}/{p.max_hp} HP"
        marker = " (you)" if p.id == player_id else ""
        party_lines.append(
            f"- {p.character_name} ({p.character_class.value.title()}) [{status}]{marker}"
        )
    party_status = "\n".join(party_lines)

    prompt = AI_PLAYER_PROMPT_TEMPLATE.format(
        character_name=player.character_name,
        character_class=player.character_class.value.title(),
        hp=player.hp,
        max_hp=player.max_hp,
        strength=player.strength,
        dexterity=player.dexterity,
        constitution=player.constitution,
        intelligence=player.intelligence,
        wisdom=player.wisdom,
        charisma=player.charisma,
        inventory=inventory_text,
        story_summary=game.story_summary or "The adventure is just beginning.",
        recent_history=recent_history,
        party_status=party_status,
    )

    api_key = get_gemini_api_key()
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    action = response.content.strip()
    logger.info(
        "AI action for %s (game=%d): %s",
        player.character_name, game_id, action[:100],
    )
    return action


def generate_ai_clarification_response(
    game_id: int,
    player_id: int,
    question: str,
    model_name: str = "gemini-2.5-flash-preview-05-20",
) -> str:
    """Generate an AI player's response to a DM clarification question."""
    player = get_player_by_id(player_id)
    if player is None:
        return "I'll go with whatever seems best."

    prompt = AI_CLARIFICATION_PROMPT.format(
        question=question,
        character_name=player.character_name,
        character_class=player.character_class.value.title(),
    )

    api_key = get_gemini_api_key()
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content.strip()


async def auto_play_turn(game_id: int, chat_id: int, bot) -> None:
    """Execute an AI turn: generate action, resolve via DM, send results to chat.

    Used both for AFK timeout auto-play and AI party member turns.
    Handles DM clarification loops (max 3 exchanges).

    Args:
        game_id: The game database ID.
        chat_id: The Telegram chat ID to send messages to.
        bot: The Telegram Bot instance for sending messages.
    """
    game = get_game_by_id(game_id)
    if game is None or game.status.value != "active":
        return

    player = get_active_player(game)
    if player is None:
        return

    # Generate and send the AI action
    action = await asyncio.to_thread(generate_ai_action, game_id, player.id)
    await bot.send_message(
        chat_id=chat_id,
        text=f"_[AI] {player.character_name}: {action}_",
        parse_mode="Markdown",
    )

    # Resolve via DM
    try:
        dm_response = await asyncio.to_thread(
            start_player_action, game, player, action
        )
    except Exception as e:
        logger.error("AI auto-play DM error for game %d: %s", game_id, e)
        await bot.send_message(chat_id=chat_id, text=f"Error resolving AI action: {e}")
        return

    # Handle clarification loop (max 3 exchanges)
    exchange_count = 0
    while not dm_response.resolved and exchange_count < 3:
        exchange_count += 1
        add_event(
            game_id=game.id,
            turn_number=game.turn_number,
            event_type=EventType.DM_CLARIFICATION,
            content=dm_response.text,
        )

        clarification_response = await asyncio.to_thread(
            generate_ai_clarification_response,
            game_id, player.id, dm_response.text,
        )
        await bot.send_message(
            chat_id=chat_id,
            text=f"_[AI] {player.character_name}: {clarification_response}_",
            parse_mode="Markdown",
        )

        try:
            dm_response = await asyncio.to_thread(
                continue_player_action, game, player,
                clarification_response, exchange_count,
            )
        except Exception as e:
            logger.error("AI clarification error for game %d: %s", game_id, e)
            await bot.send_message(chat_id=chat_id, text=f"Error: {e}")
            return

    if not dm_response.resolved:
        # Force-resolve after max clarification attempts
        dm_response.resolved = True

    # Finalize: record resolution, advance turn, narrate scene
    try:
        resolution, scene, next_player = await asyncio.to_thread(
            finalize_action, game, player, dm_response.text
        )
        await bot.send_message(chat_id=chat_id, text=resolution)
        await bot.send_message(chat_id=chat_id, text=scene)

        if next_player.is_ai:
            # Chain AI turns with a short delay
            await asyncio.sleep(5)
            await auto_play_turn(game.id, chat_id, bot)
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    f"@{next_player.telegram_username}, it's your turn! "
                    "Use /dnd_action to take your action."
                ),
            )
    except Exception as e:
        logger.error("AI finalize error for game %d: %s", game_id, e)
        await bot.send_message(chat_id=chat_id, text=f"Error finalizing AI turn: {e}")
