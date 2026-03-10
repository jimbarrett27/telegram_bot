from datetime import timedelta

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from dnd.game_manager import (
    GameManager,
    NoActiveGame,
    GameNotInLobby,
    GameNotActive,
    NotYourTurn,
    PlayerNotInGame,
    NotEnoughPlayers,
)
from dnd.models import GAME_LOBBY, GAME_ACTIVE
from dnd import database as db
from util.logging_util import setup_logger

logger = setup_logger(__name__)

# Conversation states
AWAITING_CHARACTER_NAME = 0
AWAITING_ACTION = 1

# Keyboards
NO_GAME_KEYBOARD = ReplyKeyboardMarkup(
    [["🎲 New Game"]],
    resize_keyboard=True,
)

LOBBY_KEYBOARD = ReplyKeyboardMarkup(
    [["📋 Join", "▶️ Start"]],
    resize_keyboard=True,
)

YOUR_TURN_KEYBOARD = ReplyKeyboardMarkup(
    [["⚔️ Act"], ["📜 Story", "👤 Character", "❓ Status"]],
    resize_keyboard=True,
)

NOT_YOUR_TURN_KEYBOARD = ReplyKeyboardMarkup(
    [["📜 Story", "👤 Character", "❓ Status"]],
    resize_keyboard=True,
)

CANCEL_KEYBOARD = ReplyKeyboardMarkup(
    [["🚫 Cancel"]],
    resize_keyboard=True,
)

TURN_TIMEOUT_HOURS = 24

game_manager = GameManager()


def get_keyboard(chat_id: int, user_id: int) -> ReplyKeyboardMarkup:
    game = db.get_active_game(chat_id)
    if not game:
        return NO_GAME_KEYBOARD

    if game.status == GAME_LOBBY:
        return LOBBY_KEYBOARD

    if game.status == GAME_ACTIVE:
        current = game_manager.get_current_player(chat_id)
        if current and current.user_id == user_id:
            return YOUR_TURN_KEYBOARD
        return NOT_YOUR_TURN_KEYBOARD

    return NO_GAME_KEYBOARD


def _schedule_turn_timeout(context: ContextTypes.DEFAULT_TYPE, chat_id: int, player_id: int):
    job_name = f"turn_timeout_{chat_id}"
    if context.job_queue:
        for job in context.job_queue.get_jobs_by_name(job_name):
            job.schedule_removal()
        context.job_queue.run_once(
            _turn_timeout_callback,
            when=timedelta(hours=TURN_TIMEOUT_HOURS),
            name=job_name,
            data={"chat_id": chat_id, "player_id": player_id},
        )


async def _turn_timeout_callback(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    chat_id = data["chat_id"]
    player_id = data["player_id"]

    result = await game_manager.skip_player(chat_id, player_id)
    if not result:
        return

    players = db.get_players(db.get_active_game(chat_id).id)
    skipped = next((p for p in players if p.id == player_id), None)
    name = skipped.display_name if skipped else "A player"

    await context.bot.send_message(chat_id, f"⏰ {name} took too long and was skipped.")

    if result.round_complete:
        await context.bot.send_message(chat_id, f"📖 {result.resolution}")
        await context.bot.send_message(chat_id, f"📖 {result.new_narrative}")
        if result.next_player:
            await context.bot.send_message(
                chat_id,
                f"⚔️ {result.next_player.display_name}, it's your turn!",
            )
            _schedule_turn_timeout(context, chat_id, result.next_player.id)
    elif result.next_player:
        await context.bot.send_message(
            chat_id,
            f"⚔️ {result.next_player.display_name}, it's your turn!",
        )
        _schedule_turn_timeout(context, chat_id, result.next_player.id)


# --- New Game ---

async def handle_new_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    try:
        game_manager.create_game(chat_id)
        await update.message.reply_text(
            "🎲 New game created! Players can now join.",
            reply_markup=LOBBY_KEYBOARD,
        )
    except ValueError as e:
        await update.message.reply_text(
            str(e),
            reply_markup=get_keyboard(chat_id, user_id),
        )


# --- Join (ConversationHandler) ---

async def start_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    game = db.get_active_game(chat_id)
    if not game:
        await update.message.reply_text("No active game. Create one first!", reply_markup=NO_GAME_KEYBOARD)
        return ConversationHandler.END
    if game.status != GAME_LOBBY:
        await update.message.reply_text("Game has already started.", reply_markup=get_keyboard(chat_id, user_id))
        return ConversationHandler.END

    existing = db.get_player_by_user_id(game.id, user_id)
    if existing:
        await update.message.reply_text(
            f"You're already in this game as {existing.display_name}.",
            reply_markup=LOBBY_KEYBOARD,
        )
        return ConversationHandler.END

    await update.message.reply_text("What's your character name?", reply_markup=CANCEL_KEYBOARD)
    return AWAITING_CHARACTER_NAME


async def handle_character_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    name = update.message.text.strip()

    try:
        player, is_new = game_manager.join_game(chat_id, user_id, name)
        if is_new:
            await update.message.reply_text(
                f"✅ {name} has joined the game!",
                reply_markup=LOBBY_KEYBOARD,
            )
        else:
            await update.message.reply_text(
                f"You're already in this game as {player.display_name}.",
                reply_markup=LOBBY_KEYBOARD,
            )
    except (NoActiveGame, GameNotInLobby) as e:
        await update.message.reply_text(str(e), reply_markup=get_keyboard(chat_id, user_id))

    return ConversationHandler.END


async def cancel_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    await update.message.reply_text("Join cancelled.", reply_markup=get_keyboard(chat_id, user_id))
    return ConversationHandler.END


# --- Start Game ---

async def handle_start_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    try:
        narrative, first_player = await game_manager.start_game(chat_id)
        await update.message.reply_text(f"▶️ The game begins!\n\n📖 {narrative}")
        await update.message.reply_text(
            f"⚔️ {first_player.display_name}, it's your turn!",
            reply_markup=get_keyboard(chat_id, user_id),
        )
        _schedule_turn_timeout(context, chat_id, first_player.id)
    except NoActiveGame:
        await update.message.reply_text("No game to start.", reply_markup=NO_GAME_KEYBOARD)
    except GameNotInLobby:
        await update.message.reply_text("Game has already started.", reply_markup=get_keyboard(chat_id, user_id))
    except NotEnoughPlayers:
        await update.message.reply_text("Need at least one player to start!", reply_markup=LOBBY_KEYBOARD)


# --- Act (ConversationHandler) ---

async def start_act(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    game = db.get_active_game(chat_id)
    if not game or game.status != GAME_ACTIVE:
        await update.message.reply_text("No active game.", reply_markup=get_keyboard(chat_id, user_id))
        return ConversationHandler.END

    player = db.get_player_by_user_id(game.id, user_id)
    if not player:
        await update.message.reply_text("You're not in this game.", reply_markup=get_keyboard(chat_id, user_id))
        return ConversationHandler.END

    current = game_manager.get_current_player(chat_id)
    if not current or current.user_id != user_id:
        name = current.display_name if current else "nobody"
        await update.message.reply_text(
            f"It's not your turn — waiting on {name}.",
            reply_markup=NOT_YOUR_TURN_KEYBOARD,
        )
        return ConversationHandler.END

    await update.message.reply_text("What do you do?", reply_markup=CANCEL_KEYBOARD)
    return AWAITING_ACTION


async def handle_action_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    action_text = update.message.text.strip()

    try:
        result = await game_manager.submit_action(chat_id, user_id, action_text)

        if result.round_complete:
            await update.message.reply_text(
                f"📖 {result.resolution}",
                reply_markup=get_keyboard(chat_id, user_id),
            )
            await update.message.reply_text(f"📖 {result.new_narrative}")
            if result.next_player:
                await update.message.reply_text(
                    f"⚔️ {result.next_player.display_name}, it's your turn!",
                )
                _schedule_turn_timeout(context, chat_id, result.next_player.id)
        else:
            await update.message.reply_text(
                f"✅ Action submitted!",
                reply_markup=get_keyboard(chat_id, user_id),
            )
            if result.next_player:
                await update.message.reply_text(
                    f"⚔️ {result.next_player.display_name}, it's your turn!",
                )
                _schedule_turn_timeout(context, chat_id, result.next_player.id)

    except NotYourTurn as e:
        await update.message.reply_text(str(e), reply_markup=get_keyboard(chat_id, user_id))
    except (NoActiveGame, PlayerNotInGame) as e:
        await update.message.reply_text(str(e), reply_markup=get_keyboard(chat_id, user_id))

    return ConversationHandler.END


async def cancel_act(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    await update.message.reply_text("Action cancelled.", reply_markup=get_keyboard(chat_id, user_id))
    return ConversationHandler.END


# --- Info handlers ---

async def handle_story(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    try:
        story = game_manager.get_story(chat_id)
        await update.message.reply_text(f"📜 Story so far:\n\n{story}", reply_markup=get_keyboard(chat_id, user_id))
    except NoActiveGame:
        await update.message.reply_text("No active game.", reply_markup=NO_GAME_KEYBOARD)


async def handle_character(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    player = game_manager.get_player_info(chat_id, user_id)
    if not player:
        await update.message.reply_text("You're not in this game.", reply_markup=get_keyboard(chat_id, user_id))
        return
    desc = player.character_description or "No description set."
    await update.message.reply_text(
        f"👤 {player.display_name}\n\n{desc}",
        reply_markup=get_keyboard(chat_id, user_id),
    )


async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    status = game_manager.get_status(chat_id)
    await update.message.reply_text(f"❓ {status}", reply_markup=get_keyboard(chat_id, user_id))


# --- Handlers list ---

def get_handlers():
    join_conversation = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^📋 Join$"), start_join)],
        states={
            AWAITING_CHARACTER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(r"^🚫 Cancel$"), handle_character_name),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex(r"^🚫 Cancel$"), cancel_join)],
        per_chat=True,
        per_user=True,
    )

    act_conversation = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^⚔️ Act$"), start_act)],
        states={
            AWAITING_ACTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(r"^🚫 Cancel$"), handle_action_input),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex(r"^🚫 Cancel$"), cancel_act)],
        per_chat=True,
        per_user=True,
    )

    return [
        join_conversation,
        act_conversation,
        MessageHandler(filters.Regex(r"^🎲 New Game$"), handle_new_game),
        MessageHandler(filters.Regex(r"^▶️ Start$"), handle_start_game),
        MessageHandler(filters.Regex(r"^📜 Story$"), handle_story),
        MessageHandler(filters.Regex(r"^👤 Character$"), handle_character),
        MessageHandler(filters.Regex(r"^❓ Status$"), handle_status),
    ]
