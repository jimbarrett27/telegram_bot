"""
Game logic for the D&D async game system.

Handles turn management, LLM context building, and narration/resolution calls.
"""

import json
from typing import Optional

from dnd.models import Game, Player, GameEvent, EventType, GameStatus
from dnd.database import (
    get_game_by_chat,
    get_recent_events,
    update_game_current_player,
    update_game_status,
    update_game_adventure,
    update_player_hp,
    add_event,
    get_player_by_id,
)
from llm.llm_util import get_llm_response
from util.constants import REPO_ROOT
from util.logging_util import setup_logger

logger = setup_logger(__name__)

PROMPTS_DIR = REPO_ROOT / "dnd/prompts"
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


def _build_player_dicts(players: list[Player]) -> list[dict]:
    """Build player info dicts for prompt templates."""
    return [
        {
            "character_name": p.character_name,
            "character_class": p.character_class.value,
            "hp": p.hp,
            "max_hp": p.max_hp,
            "telegram_username": p.telegram_username,
        }
        for p in players
    ]


def _build_event_dicts(events: list[GameEvent]) -> list[dict]:
    """Build event info dicts for prompt templates."""
    return [
        {
            "event_type": e.event_type.value,
            "content": e.content,
        }
        for e in events
    ]


def generate_intro(game: Game, active_player: Player) -> str:
    """Generate the adventure intro narration using LLM."""
    template_path = str(PROMPTS_DIR / "generate_adventure_intro.jinja2")
    params = {
        "adventure_text": game.adventure_text,
        "players": _build_player_dicts(game.players),
        "active_player": {
            "character_name": active_player.character_name,
            "telegram_username": active_player.telegram_username,
        },
    }

    narration = get_llm_response(template_path, params)

    # Record the narration as an event
    add_event(
        game_id=game.id,
        turn_number=game.turn_number,
        event_type=EventType.NARRATION,
        content=narration,
    )

    return narration


def narrate_scene(game: Game, active_player: Player) -> str:
    """Generate scene narration for the active player's turn."""
    events = get_recent_events(game.id, limit=30)
    template_path = str(PROMPTS_DIR / "narrate_scene.jinja2")
    params = {
        "adventure_text": game.adventure_text,
        "players": _build_player_dicts(game.players),
        "events": _build_event_dicts(events),
        "active_player": {
            "character_name": active_player.character_name,
            "telegram_username": active_player.telegram_username,
        },
    }

    narration = get_llm_response(template_path, params)

    add_event(
        game_id=game.id,
        turn_number=game.turn_number,
        event_type=EventType.NARRATION,
        content=narration,
    )

    return narration


def resolve_action(game: Game, active_player: Player, action_text: str) -> str:
    """Resolve a player's action using LLM. Returns the narration text."""
    # Record the player's action
    add_event(
        game_id=game.id,
        turn_number=game.turn_number,
        event_type=EventType.PLAYER_ACTION,
        content=action_text,
        actor_player_id=active_player.id,
    )

    events = get_recent_events(game.id, limit=30)
    template_path = str(PROMPTS_DIR / "resolve_action.jinja2")
    params = {
        "adventure_text": game.adventure_text,
        "players": _build_player_dicts(game.players),
        "events": _build_event_dicts(events),
        "active_player": {
            "character_name": active_player.character_name,
            "character_class": active_player.character_class.value,
            "telegram_username": active_player.telegram_username,
        },
        "action_text": action_text,
    }

    response = get_llm_response(template_path, params)

    # Parse JSON response
    try:
        clean = response.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse LLM response as JSON: {response}")
        # Treat the whole response as narration with no HP changes
        result = {"narration": response, "hp_changes": []}

    narration = result.get("narration", response)
    hp_changes = result.get("hp_changes", [])

    # Apply HP changes
    for change in hp_changes:
        player_name = change.get("player_name")
        delta = change.get("change", 0)
        if not player_name or delta == 0:
            continue

        for p in game.players:
            if p.character_name == player_name:
                new_hp = max(0, min(p.max_hp, p.hp + delta))
                update_player_hp(p.id, new_hp)
                break

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
