"""
Game logic for the D&D async game system.

Handles turn management and delegates narration/resolution to the DM agent.
"""

from typing import Optional

from langchain_core.messages import HumanMessage

from dnd.models import Game, Player, GameEvent, EventType, GameStatus
from dnd.database import (
    get_game_by_chat,
    get_recent_events,
    update_game_current_player,
    update_game_status,
    update_game_adventure,
    add_event,
)
from dnd.dm_agent import create_dm_agent
from util.constants import REPO_ROOT
from util.logging_util import setup_logger

logger = setup_logger(__name__)

ADVENTURES_DIR = REPO_ROOT / "dnd/adventures"


def get_adventure_text() -> str:
    """Load the placeholder adventure text."""
    path = ADVENTURES_DIR / "placeholder.txt"
    with open(path, "r") as f:
        return f.read()


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


def generate_intro(game: Game, active_player: Player) -> str:
    """Generate the adventure intro narration using the DM agent."""
    message = (
        f"Generate an exciting opening narration for this adventure. "
        f"The party has just arrived at the adventure location. "
        f"Set the scene and atmosphere in 2-3 paragraphs. "
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


def start_game(game: Game) -> tuple[str, Player]:
    """Start a game: set adventure, activate, generate intro. Returns (narration, first_player)."""
    adventure_text = get_adventure_text()
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
