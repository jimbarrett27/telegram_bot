"""
Turn timeout checker for D&D games.

Runs as a job_queue repeating task. When a player hasn't acted for 24 hours,
the AI takes over for that turn.
"""

import logging

from telegram.ext import ContextTypes

from dnd.database import get_stale_active_games
from dnd.game_logic import get_active_player
from dnd.ai_player import auto_play_turn

logger = logging.getLogger(__name__)

TURN_TIMEOUT_SECONDS = 86400  # 24 hours


async def check_turn_timeouts(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job queue callback: find stale turns and auto-play them.

    Runs every few minutes. For each active game where the current turn
    has been idle for more than TURN_TIMEOUT_SECONDS, sends a timeout
    warning and triggers an AI auto-play.
    """
    try:
        stale_games = get_stale_active_games(TURN_TIMEOUT_SECONDS)
    except Exception as e:
        logger.error("Error checking stale games: %s", e)
        return

    for game in stale_games:
        player = get_active_player(game)
        if player is None:
            continue

        # Skip if the active player is already AI-controlled
        # (AI turns are handled immediately, so staleness means something went wrong)
        if player.is_ai:
            logger.warning(
                "Stale AI turn detected for game %d, player %s — retrying",
                game.id, player.character_name,
            )

        logger.info(
            "Turn timeout for game %d (chat %d), player %s",
            game.id, game.chat_id, player.character_name,
        )

        try:
            timeout_msg = (
                f"⏰ {player.character_name} hasn't acted in 24 hours. "
                "The AI takes over for this turn."
            )
            await context.bot.send_message(chat_id=game.chat_id, text=timeout_msg)
            await auto_play_turn(game.id, game.chat_id, context.bot)
        except Exception as e:
            logger.error(
                "Error auto-playing timeout for game %d: %s", game.id, e
            )
