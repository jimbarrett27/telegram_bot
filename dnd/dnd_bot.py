"""
Telegram command handlers for the D&D async game system.
"""

import asyncio

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

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
from dnd.game_logic import (
    get_active_player,
    start_game,
    process_action,
)
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
    await update.message.reply_text(
        "A new D&D adventure has been created! "
        "Players can join with /dnd_join <name> <class>\n"
        f"Available classes: {', '.join(VALID_CLASSES)}\n"
        "Start the adventure with /dnd_start (needs 2-4 players)."
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

    await update.message.reply_text("The adventure begins! Generating the opening scene...")

    try:
        narration, first_player = await asyncio.to_thread(start_game, game)
        await update.message.reply_text(narration)
        await update.message.reply_text(
            f"@{first_player.telegram_username}, it's your turn! "
            "Use /dnd_action <what you do> to take your action."
        )
    except Exception as e:
        logger.error(f"Error starting game: {e}")
        await update.message.reply_text(f"Error starting the adventure: {e}")


async def dnd_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Take an action on your turn."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    game = get_game_by_chat(chat_id)
    if game is None:
        await update.message.reply_text("No game in this chat.")
        return

    if game.status != GameStatus.ACTIVE:
        await update.message.reply_text("The game hasn't started yet.")
        return

    active_player = get_active_player(game)
    if active_player is None:
        await update.message.reply_text("Error: no active player found.")
        return

    player = get_player_by_user(game.id, user.id)
    if player is None:
        await update.message.reply_text("You're not in this game.")
        return

    if player.id != active_player.id:
        await update.message.reply_text(
            f"It's not your turn. Waiting for {active_player.character_name} "
            f"(@{active_player.telegram_username})."
        )
        return

    if not context.args:
        await update.message.reply_text("Usage: /dnd_action <what you want to do>")
        return

    action_text = " ".join(context.args)

    await update.message.reply_text("Resolving your action...")

    try:
        resolution, scene, next_player = await asyncio.to_thread(
            process_action, game, player, action_text
        )

        await update.message.reply_text(resolution)
        await update.message.reply_text(scene)
        await update.message.reply_text(
            f"@{next_player.telegram_username}, it's your turn! "
            "Use /dnd_action <what you do> to take your action."
        )
    except Exception as e:
        logger.error(f"Error processing action: {e}")
        await update.message.reply_text(f"Error resolving action: {e}")


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
    return [
        CommandHandler("dnd_new", dnd_new),
        CommandHandler("dnd_join", dnd_join),
        CommandHandler("dnd_start", dnd_start),
        CommandHandler("dnd_action", dnd_action),
        CommandHandler("dnd_sheet", dnd_sheet),
        CommandHandler("dnd_status", dnd_status),
        CommandHandler("dnd_end", dnd_end),
    ]
