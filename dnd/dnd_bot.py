"""
Telegram command handlers for the D&D async game system.
"""

import asyncio

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from dnd.models import GameStatus, CharacterClass
from dnd.database import (
    create_game,
    get_game_by_chat,
    add_player,
    add_inventory_item,
    create_spell_slots,
    get_player_by_user,
    get_player_inventory,
    get_spell_slots,
    delete_game,
)
from dnd.character_templates import get_template
from dnd.models import EventType
from dnd.database import add_event
from dnd.game_logic import (
    get_active_player,
    start_game,
    process_action,
    start_player_action,
    continue_player_action,
    finalize_action,
)
from dnd.pdf_parser import list_available_adventures
from util.logging_util import setup_logger

logger = setup_logger(__name__)

VALID_CLASSES = {c.value for c in CharacterClass}


async def dnd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a new D&D game in this group chat."""
    chat_id = update.effective_chat.id

    existing = get_game_by_chat(chat_id)
    if existing is not None:
        await update.message.reply_text(
            f"A game already exists in this chat (status: {existing.status.value}). "
            "Use /dnd_end to end it first."
        )
        return

    game = create_game(chat_id)

    adventures = list_available_adventures()
    adventure_line = ""
    if adventures:
        adventure_line = f"\nAvailable adventures: {', '.join(adventures)}\n"

    await update.message.reply_text(
        "A new D&D adventure has been created! "
        "Players can join with /dnd_join <name> <class>\n"
        f"Available classes: {', '.join(VALID_CLASSES)}"
        f"{adventure_line}\n"
        "Start the adventure with /dnd_start [adventure_name] (needs 2-4 players)."
    )


async def dnd_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Join the current game with a character."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    game = get_game_by_chat(chat_id)
    if game is None:
        await update.message.reply_text("No game in this chat. Use /dnd_new to create one.")
        return

    if game.status != GameStatus.RECRUITING:
        await update.message.reply_text("The game has already started. Can't join now.")
        return

    if len(game.players) >= 4:
        await update.message.reply_text("The party is full (4/4 players).")
        return

    existing_player = get_player_by_user(game.id, user.id)
    if existing_player is not None:
        await update.message.reply_text("You've already joined this game.")
        return

    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text(
            "Usage: /dnd_join <character_name> <class>\n"
            f"Available classes: {', '.join(VALID_CLASSES)}"
        )
        return

    character_name = args[0]
    class_str = args[1].lower()

    if class_str not in VALID_CLASSES:
        await update.message.reply_text(
            f"Invalid class '{class_str}'. Available: {', '.join(VALID_CLASSES)}"
        )
        return

    character_class = CharacterClass(class_str)
    template = get_template(character_class)
    attrs = template["attributes"]

    player = add_player(
        game_id=game.id,
        telegram_user_id=user.id,
        telegram_username=user.username or user.first_name,
        character_name=character_name,
        character_class=character_class,
        hp=template["hp"],
        max_hp=template["max_hp"],
        **attrs,
    )

    # Set up starting inventory
    for item in template["starting_inventory"]:
        add_inventory_item(
            player_id=player.id,
            game_id=game.id,
            item_name=item["item_name"],
            item_type=item["item_type"],
            quantity=item["quantity"],
            equipped=item.get("equipped", False),
        )

    # Set up spell slots
    if template["spell_slots"]:
        create_spell_slots(player_id=player.id, **template["spell_slots"])

    player_count = len(game.players) + 1
    await update.message.reply_text(
        f"{character_name} the {class_str.title()} has joined the party! "
        f"({player_count}/4 players)"
    )


async def dnd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the adventure."""
    chat_id = update.effective_chat.id

    game = get_game_by_chat(chat_id)
    if game is None:
        await update.message.reply_text("No game in this chat. Use /dnd_new to create one.")
        return

    if game.status != GameStatus.RECRUITING:
        await update.message.reply_text("The game has already started.")
        return

    if len(game.players) < 2:
        await update.message.reply_text(
            f"Need at least 2 players to start (currently {len(game.players)}). "
            "Use /dnd_join to add more."
        )
        return

    adventure_name = None
    if context.args:
        adventure_name = " ".join(context.args)

    loading_msg = "The adventure begins!"
    if adventure_name:
        loading_msg += f" Loading '{adventure_name}'..."
    else:
        loading_msg += " Generating the opening scene..."
    await update.message.reply_text(loading_msg)

    try:
        narration, first_player = await asyncio.to_thread(start_game, game, adventure_name)
        await update.message.reply_text(narration)
        await update.message.reply_text(
            f"@{first_player.telegram_username}, it's your turn! "
            "Use /dnd_action to take your action."
        )
    except FileNotFoundError as e:
        await update.message.reply_text(str(e))
    except Exception as e:
        logger.error(f"Error starting game: {e}")
        await update.message.reply_text(f"Error starting the adventure: {e}")


# --- Conversational action flow ---

AWAITING_ACTION = 0
AWAITING_CLARIFICATION = 1

# Keys used in context.chat_data during a conversation
_CD_GAME_ID = "dnd_action_game_id"
_CD_PLAYER_ID = "dnd_action_player_id"
_CD_USER_ID = "dnd_action_user_id"
_CD_EXCHANGE_COUNT = "dnd_action_exchange_count"

_CHAT_DATA_KEYS = [_CD_GAME_ID, _CD_PLAYER_ID, _CD_USER_ID, _CD_EXCHANGE_COUNT]


def _cleanup_chat_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove conversation state from chat_data."""
    for key in _CHAT_DATA_KEYS:
        context.chat_data.pop(key, None)


async def _send_resolution(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    game,
    player,
    resolution_text: str,
) -> int:
    """Finalize the action, send resolution + scene + next player prompt."""
    try:
        resolution, scene, next_player = await asyncio.to_thread(
            finalize_action, game, player, resolution_text
        )
        await update.message.reply_text(resolution)
        await update.message.reply_text(scene)
        await update.message.reply_text(
            f"@{next_player.telegram_username}, it's your turn! "
            "Use /dnd_action to take your action."
        )
    except Exception as e:
        logger.error(f"Error finalizing action: {e}")
        await update.message.reply_text(f"Error: {e}")

    _cleanup_chat_data(context)
    return ConversationHandler.END


async def _handle_action_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    game,
    player,
    action_text: str,
) -> int:
    """Process action text — shared by entry-with-args and AWAITING_ACTION state."""
    await update.message.reply_text("The DM considers your action...")

    try:
        dm_response = await asyncio.to_thread(
            start_player_action, game, player, action_text
        )
    except Exception as e:
        logger.error(f"Error processing action: {e}")
        await update.message.reply_text(f"Error resolving action: {e}")
        _cleanup_chat_data(context)
        return ConversationHandler.END

    if dm_response.resolved:
        return await _send_resolution(update, context, game, player, dm_response.text)

    # DM is asking for clarification
    add_event(
        game_id=game.id,
        turn_number=game.turn_number,
        event_type=EventType.DM_CLARIFICATION,
        content=dm_response.text,
    )
    await update.message.reply_text(dm_response.text)

    context.chat_data[_CD_GAME_ID] = game.id
    context.chat_data[_CD_PLAYER_ID] = player.id
    context.chat_data[_CD_USER_ID] = update.effective_user.id
    context.chat_data[_CD_EXCHANGE_COUNT] = 1

    return AWAITING_CLARIFICATION


async def dnd_action_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /dnd_action. Validates turn, prompts for action."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    game = get_game_by_chat(chat_id)
    if game is None:
        await update.message.reply_text("No game in this chat.")
        return ConversationHandler.END

    if game.status != GameStatus.ACTIVE:
        await update.message.reply_text("The game hasn't started yet.")
        return ConversationHandler.END

    active_player = get_active_player(game)
    if active_player is None:
        await update.message.reply_text("Error: no active player found.")
        return ConversationHandler.END

    player = get_player_by_user(game.id, user.id)
    if player is None:
        await update.message.reply_text("You're not in this game.")
        return ConversationHandler.END

    if player.id != active_player.id:
        await update.message.reply_text(
            f"It's not your turn. Waiting for {active_player.character_name} "
            f"(@{active_player.telegram_username})."
        )
        return ConversationHandler.END

    # Backwards compatible: /dnd_action <text> skips the prompt
    if context.args:
        action_text = " ".join(context.args)
        return await _handle_action_text(update, context, game, player, action_text)

    # No args — prompt the player (fixes #1 auto-send issue)
    await update.message.reply_text(
        f"{player.character_name}, what do you want to do?\n"
        "(Type your action, or /dnd_cancel to cancel)"
    )

    context.chat_data[_CD_GAME_ID] = game.id
    context.chat_data[_CD_PLAYER_ID] = player.id
    context.chat_data[_CD_USER_ID] = user.id
    context.chat_data[_CD_EXCHANGE_COUNT] = 0

    return AWAITING_ACTION


async def dnd_action_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive the player's action text (AWAITING_ACTION state)."""
    user_id = update.effective_user.id
    if user_id != context.chat_data.get(_CD_USER_ID):
        return AWAITING_ACTION  # Ignore messages from other users

    action_text = update.message.text
    game = get_game_by_chat(update.effective_chat.id)
    player = get_player_by_user(game.id, user_id)

    return await _handle_action_text(update, context, game, player, action_text)


async def dnd_action_clarification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle player's response to a DM clarification (AWAITING_CLARIFICATION state)."""
    user_id = update.effective_user.id
    if user_id != context.chat_data.get(_CD_USER_ID):
        return AWAITING_CLARIFICATION  # Ignore other users

    response_text = update.message.text
    game = get_game_by_chat(update.effective_chat.id)
    player = get_player_by_user(game.id, user_id)
    exchange_count = context.chat_data.get(_CD_EXCHANGE_COUNT, 0)

    await update.message.reply_text("The DM considers your response...")

    try:
        dm_response = await asyncio.to_thread(
            continue_player_action, game, player, response_text, exchange_count
        )
    except Exception as e:
        logger.error(f"Error processing clarification: {e}")
        await update.message.reply_text(f"Error: {e}")
        _cleanup_chat_data(context)
        return ConversationHandler.END

    if dm_response.resolved:
        return await _send_resolution(update, context, game, player, dm_response.text)

    # Another clarification question
    add_event(
        game_id=game.id,
        turn_number=game.turn_number,
        event_type=EventType.DM_CLARIFICATION,
        content=dm_response.text,
    )
    await update.message.reply_text(dm_response.text)

    context.chat_data[_CD_EXCHANGE_COUNT] = exchange_count + 1

    return AWAITING_CLARIFICATION


async def dnd_action_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the current action conversation."""
    _cleanup_chat_data(context)
    await update.message.reply_text("Action cancelled. Use /dnd_action to try again.")
    return ConversationHandler.END


async def dnd_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View your character sheet."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    game = get_game_by_chat(chat_id)
    if game is None:
        await update.message.reply_text("No game in this chat.")
        return

    player = get_player_by_user(game.id, user.id)
    if player is None:
        await update.message.reply_text("You're not in this game.")
        return

    # Ability scores with modifiers
    def _mod(score):
        m = (score - 10) // 2
        return f"+{m}" if m >= 0 else str(m)

    sheet_lines = [
        f"--- Character Sheet ---",
        f"Name: {player.character_name}",
        f"Class: {player.character_class.value.title()}",
        f"Level: {player.level}",
        f"HP: {player.hp}/{player.max_hp}",
        f"",
        f"--- Ability Scores ---",
        f"STR: {player.strength} ({_mod(player.strength)})  DEX: {player.dexterity} ({_mod(player.dexterity)})",
        f"CON: {player.constitution} ({_mod(player.constitution)})  INT: {player.intelligence} ({_mod(player.intelligence)})",
        f"WIS: {player.wisdom} ({_mod(player.wisdom)})  CHA: {player.charisma} ({_mod(player.charisma)})",
    ]

    # Inventory
    items = get_player_inventory(player.id)
    if items:
        sheet_lines.append("")
        sheet_lines.append("--- Inventory ---")
        for item in items:
            equipped = " [E]" if item.equipped else ""
            qty = f" x{item.quantity}" if item.quantity > 1 else ""
            sheet_lines.append(f"  {item.item_name}{qty}{equipped}")

    # Spell slots
    slots = get_spell_slots(player.id)
    if slots:
        has_slots = any(getattr(slots, f"max_level_{i}") > 0 for i in range(1, 10))
        if has_slots:
            sheet_lines.append("")
            sheet_lines.append("--- Spell Slots ---")
            for lvl in range(1, 10):
                current = getattr(slots, f"level_{lvl}")
                maximum = getattr(slots, f"max_level_{lvl}")
                if maximum > 0:
                    sheet_lines.append(f"  Level {lvl}: {current}/{maximum}")

    await update.message.reply_text("\n".join(sheet_lines))


async def dnd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show game status and party info."""
    chat_id = update.effective_chat.id

    game = get_game_by_chat(chat_id)
    if game is None:
        await update.message.reply_text("No game in this chat. Use /dnd_new to create one.")
        return

    lines = [f"--- D&D Game Status ---", f"Status: {game.status.value.title()}"]

    if game.players:
        lines.append(f"\nParty ({len(game.players)}/4):")
        for p in game.players:
            marker = ""
            if game.status == GameStatus.ACTIVE and p.id == game.current_player_id:
                marker = " <-- active"
            lines.append(
                f"  {p.character_name} ({p.character_class.value.title()}) "
                f"HP: {p.hp}/{p.max_hp} @{p.telegram_username}{marker}"
            )
    else:
        lines.append("\nNo players yet. Use /dnd_join to join!")

    if game.status == GameStatus.ACTIVE:
        lines.append(f"\nTurn: {game.turn_number}")

    await update.message.reply_text("\n".join(lines))


async def dnd_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """End the current game."""
    chat_id = update.effective_chat.id

    game = get_game_by_chat(chat_id)
    if game is None:
        await update.message.reply_text("No game in this chat.")
        return

    delete_game(chat_id)
    await update.message.reply_text("The adventure has ended. Use /dnd_new to start a new one.")


def get_handlers() -> list:
    """Return all D&D command handlers for registration."""
    action_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("dnd_action", dnd_action_start),
        ],
        states={
            AWAITING_ACTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, dnd_action_receive),
            ],
            AWAITING_CLARIFICATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, dnd_action_clarification),
            ],
        },
        fallbacks=[
            CommandHandler("dnd_cancel", dnd_action_cancel),
        ],
        per_chat=True,
        per_user=True,
        name="dnd_action_conversation",
        persistent=False,
    )

    return [
        CommandHandler("dnd_new", dnd_new),
        CommandHandler("dnd_join", dnd_join),
        CommandHandler("dnd_start", dnd_start),
        action_conversation,
        CommandHandler("dnd_sheet", dnd_sheet),
        CommandHandler("dnd_status", dnd_status),
        CommandHandler("dnd_end", dnd_end),
    ]
