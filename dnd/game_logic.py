"""
Game logic for the D&D async game system.

Handles turn management and delegates narration/resolution to the DM agent.
"""

from dataclasses import dataclass
from typing import Optional

from langchain_core.messages import HumanMessage

from dnd.models import Game, Player, GameEvent, EventType, GameStatus
from dnd.database import (
    get_game_by_chat,
    get_recent_events,
    update_game_current_player,
    update_game_status,
    update_game_adventure,
    store_campaign_sections,
    add_event,
)
from dnd.dm_agent import create_dm_agent
from dnd.summarizer import summarize_events
from dnd.campaign_loader import load_campaign, list_available_campaigns
from util.logging_util import setup_logger

logger = setup_logger(__name__)


def get_active_player(game: Game) -> Optional[Player]:
    """Get the currently active player from the game."""
    if game.current_player_id is None:
        return None
    for player in game.players:
        if player.id == game.current_player_id:
            return player
    return None


def advance_turn(game: Game) -> Player:
    """Advance to the next player in round-robin order. Returns the new active player."""
    if not game.players:
        raise ValueError("No players in game")

    if game.current_player_id is None:
        # First turn - pick the first player
        next_player = game.players[0]
        new_turn = 1
    else:
        # Find current player index and advance
        current_idx = None
        for i, p in enumerate(game.players):
            if p.id == game.current_player_id:
                current_idx = i
                break

        if current_idx is None:
            next_player = game.players[0]
        else:
            next_idx = (current_idx + 1) % len(game.players)
            next_player = game.players[next_idx]

        new_turn = game.turn_number + 1

    update_game_current_player(game.id, next_player.id, new_turn)
    return next_player


def _invoke_dm(game_id: int, message: str) -> str:
    """Create a DM agent and invoke it with a message. Returns the response text."""
    agent = create_dm_agent(game_id)
    return agent.get_response_text([HumanMessage(content=message)])


CLARIFICATION_MARKER = "CLARIFICATION_REQUESTED: "

DICE_RETRY_MESSAGE = (
    "You resolved the previous action without rolling dice. "
    "You MUST use the roll_dice tool for attack rolls, skill checks, saving throws, "
    "and damage rolls. Re-resolve this action properly: "
    "announce the check, call roll_dice, then narrate the result based on the roll."
)


@dataclass
class DMResponse:
    """Result of a DM agent invocation."""
    resolved: bool  # True = action resolved, False = clarification requested
    text: str       # DM's narration or clarification question


def _extract_tools_used(messages: list) -> dict[str, int]:
    """Scan LangGraph message history and count tool invocations by name."""
    tools = {}
    for msg in messages:
        if getattr(msg, "type", None) == "tool":
            name = getattr(msg, "name", None)
            if name:
                tools[name] = tools.get(name, 0) + 1
    return tools


def _needs_dice_retry(tools_used: dict[str, int]) -> bool:
    """Check if the DM applied damage without rolling dice.

    Returns True if apply_damage was called but roll_dice was not,
    indicating the DM skipped mandatory dice rolls.
    """
    has_damage = tools_used.get("apply_damage", 0) > 0
    has_dice = tools_used.get("roll_dice", 0) > 0
    return has_damage and not has_dice


def _extract_response(all_messages: list) -> tuple[bool, str]:
    """Extract clarification status and response text from agent messages."""
    clarification_requested = False
    for msg in all_messages:
        if (getattr(msg, "type", None) == "tool"
                and getattr(msg, "name", None) == "request_clarification"):
            clarification_requested = True
            break

    response_text = ""
    for msg in reversed(all_messages):
        if getattr(msg, "type", None) == "ai" and msg.content:
            content = msg.content
            if isinstance(content, list):
                text_parts = [
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and "text" in part
                ]
                response_text = "".join(text_parts)
            else:
                response_text = content
            break

    if not response_text:
        response_text = "The Dungeon Master is silent..."

    return clarification_requested, response_text


def _invoke_dm_conversational(game_id: int, message: str) -> DMResponse:
    """Invoke the DM agent and detect whether it resolved or asked for clarification.

    Scans tool messages for the request_clarification marker.
    If the DM resolved with damage but no dice rolls, retries once with enforcement.
    """
    agent = create_dm_agent(game_id)
    result = agent.invoke([HumanMessage(content=message)])
    all_messages = result["messages"]

    tools_used = _extract_tools_used(all_messages)
    clarification_requested, response_text = _extract_response(all_messages)

    # If resolved with damage but no dice, retry once
    if not clarification_requested and _needs_dice_retry(tools_used):
        logger.warning(
            "DM resolved action without dice rolls (game=%d). Retrying with enforcement.",
            game_id,
        )
        retry_agent = create_dm_agent(game_id)
        retry_msg = f"{message}\n\n{DICE_RETRY_MESSAGE}"
        retry_result = retry_agent.invoke([HumanMessage(content=retry_msg)])
        retry_messages = retry_result["messages"]

        clarification_requested, response_text = _extract_response(retry_messages)

    return DMResponse(resolved=not clarification_requested, text=response_text)


def start_player_action(game: Game, player: Player, action_text: str) -> DMResponse:
    """Begin resolving a player's action. Returns DMResponse indicating resolve or clarify."""
    add_event(
        game_id=game.id,
        turn_number=game.turn_number,
        event_type=EventType.PLAYER_ACTION,
        content=action_text,
        actor_player_id=player.id,
    )

    message = (
        f"{player.character_name} ({player.character_class.value.title()}) "
        f"attempts: \"{action_text}\"\n\n"
        f"Resolve this action. Use roll_dice for any checks or attack rolls. "
        f"Use apply_damage if anyone takes damage or receives healing. "
        f"If the action is ambiguous, use request_clarification to ask the player. "
        f"Otherwise, resolve and narrate the outcome."
    )

    return _invoke_dm_conversational(game.id, message)


def continue_player_action(
    game: Game,
    player: Player,
    response_text: str,
    exchange_count: int,
) -> DMResponse:
    """Continue resolving after player responds to clarification."""
    add_event(
        game_id=game.id,
        turn_number=game.turn_number,
        event_type=EventType.PLAYER_CLARIFICATION,
        content=response_text,
        actor_player_id=player.id,
    )

    force_resolve = exchange_count >= 25
    suffix = ""
    if force_resolve:
        suffix = (
            "\n\nIMPORTANT: You have asked enough questions. "
            "You must resolve this action NOW with the information you have. "
            "Do not call request_clarification."
        )

    message = (
        f"{player.character_name} responds: \"{response_text}\"\n\n"
        f"Continue resolving this action based on the player's response and "
        f"the conversation history in your recent events.{suffix}"
    )

    return _invoke_dm_conversational(game.id, message)


def finalize_action(game: Game, player: Player, resolution_text: str) -> tuple[str, str, Player]:
    """Finalize a resolved action: record event, advance turn, narrate scene."""
    add_event(
        game_id=game.id,
        turn_number=game.turn_number,
        event_type=EventType.RESOLUTION,
        content=resolution_text,
    )

    # Update the running story summary after each resolution
    try:
        summarize_events(game.id)
    except Exception:
        logger.exception("Failed to summarize events for game_id=%d", game.id)

    next_player = advance_turn(game)

    # Reload game for updated state
    game = get_game_by_chat(game.chat_id)
    scene = narrate_scene(game, next_player)

    return resolution_text, scene, next_player


def generate_intro(game: Game, active_player: Player) -> str:
    """Generate the adventure intro narration using the DM agent."""
    message = (
        f"Generate an opening narration for this adventure. "
        f"The party has just arrived at the adventure location. "
        f"Set the scene in 2-3 short paragraphs. Keep it grounded and understated. "
        f"The first player to act is {active_player.character_name} "
        f"(@{active_player.telegram_username}). "
        f"End by prompting them to decide their first action."
    )

    narration = _invoke_dm(game.id, message)

    add_event(
        game_id=game.id,
        turn_number=game.turn_number,
        event_type=EventType.NARRATION,
        content=narration,
    )

    return narration


def narrate_scene(game: Game, active_player: Player) -> str:
    """Generate scene narration for the active player's turn."""
    message = (
        f"It is now {active_player.character_name}'s turn "
        f"(@{active_player.telegram_username}). "
        f"Narrate the current scene briefly (1-2 paragraphs) based on what just happened, "
        f"and prompt them to decide their action."
    )

    narration = _invoke_dm(game.id, message)

    add_event(
        game_id=game.id,
        turn_number=game.turn_number,
        event_type=EventType.NARRATION,
        content=narration,
    )

    return narration


def resolve_action(game: Game, active_player: Player, action_text: str) -> str:
    """Resolve a player's action using the DM agent. Returns the narration text.

    The agent will use its tools (roll_dice, apply_damage, etc.) during
    the ReAct loop to determine outcomes. HP changes are applied via the
    apply_damage tool, not via JSON parsing.
    """
    # Record the player's action
    add_event(
        game_id=game.id,
        turn_number=game.turn_number,
        event_type=EventType.PLAYER_ACTION,
        content=action_text,
        actor_player_id=active_player.id,
    )

    message = (
        f"{active_player.character_name} ({active_player.character_class.value.title()}) "
        f"attempts: \"{action_text}\"\n\n"
        f"Resolve this action. Use roll_dice for any checks or attack rolls. "
        f"Use apply_damage if anyone takes damage or receives healing. "
        f"Then narrate the outcome."
    )

    narration = _invoke_dm(game.id, message)

    # Record the resolution
    add_event(
        game_id=game.id,
        turn_number=game.turn_number,
        event_type=EventType.RESOLUTION,
        content=narration,
    )

    return narration


def start_game(game: Game, adventure_name: str | None = None) -> tuple[str, Player]:
    """Start a game: set adventure, activate, generate intro. Returns (narration, first_player).

    Args:
        game: The game to start.
        adventure_name: Optional campaign name. If None, defaults to 'goblin_caves'.
    """
    campaign = adventure_name or "goblin_caves"
    adventure_text = load_campaign(game.id, campaign)
    update_game_adventure(game.id, adventure_text)
    update_game_status(game.id, GameStatus.ACTIVE)
    game.adventure_text = adventure_text

    first_player = advance_turn(game)

    # Reload game to get updated state
    game = get_game_by_chat(game.chat_id)
    narration = generate_intro(game, first_player)

    return narration, first_player


def process_action(game: Game, player: Player, action_text: str) -> tuple[str, str, Player]:
    """Process a player action. Returns (resolution_narration, scene_narration, next_player)."""
    resolution = resolve_action(game, player, action_text)

    # Advance to next player
    next_player = advance_turn(game)

    # Reload game for updated HP values
    game = get_game_by_chat(game.chat_id)
    scene = narrate_scene(game, next_player)

    return resolution, scene, next_player
