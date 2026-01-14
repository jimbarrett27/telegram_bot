from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from gcp_util.secrets import get_telegram_bot_key
from swedish.database import init_db as init_swedish_db, populate_db
from swedish import swedish_bot
from content_screening.database import init_db as init_screening_db
from content_screening import screening_bot
from minecraft.react_to_logs import react_to_logs as react_to_minecraft_logs
from content_screening.scanner import run_daily_scan_if_due
from util.logging_util import setup_logger, log_telegram_message_received

logger = setup_logger(__name__)

# Main menu keyboard
MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🇸🇪 Practise", "📝 Add Word"],
        ["📚 Papers Status", "🔍 Scan Papers"],
        ["❓ Help"],
    ],
    resize_keyboard=True,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message with the main menu keyboard."""
    await update.message.reply_text(
        "Welcome! Choose an option:",
        reply_markup=MAIN_MENU_KEYBOARD,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message."""
    help_text = """Available commands:

🇸🇪 Swedish Learning:
• 🇸🇪 Practise - Practice a random flashcard
• 📝 Add Word - Add a new word to your dictionary
• sv add <type> <word> - Add word directly (type: noun, verb, adj, auto)
• sv practise - Start practice directly

📚 Papers:
• 📚 Papers Status - Show pending articles
• 🔍 Scan Papers - Scan ArXiv and RSS feeds
• papers status / papers scan - Text commands

Use /start to show the menu keyboard."""
    await update.message.reply_text(help_text, reply_markup=MAIN_MENU_KEYBOARD)


async def handle_papers_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle papers status button."""
    log_telegram_message_received(logger, str(update.effective_chat.id),
                                  update.effective_user.username or "unknown",
                                  update.message.text)
    await screening_bot.handle_status_async(update, context)


async def handle_papers_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle papers scan button - scans all feeds (ArXiv and RSS)."""
    log_telegram_message_received(logger, str(update.effective_chat.id),
                                  update.effective_user.username or "unknown",
                                  update.message.text)
    await screening_bot.handle_scan_async(update, context, scan_type="all")


async def handle_text_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text-based commands (sv ..., papers ...)."""
    text = update.message.text
    chat_id = update.effective_chat.id
    username = update.effective_user.username or "unknown"

    log_telegram_message_received(logger, str(chat_id), username, text)

    command = text.split()[0].lower()

    if command in ("sv", "🇸🇪"):
        rest = ' '.join(text.split()[1:]).strip()
        await swedish_bot.handle_text_command_async(update, context, rest)
    elif command == "papers":
        rest = ' '.join(text.split()[1:]).strip()
        await screening_bot.handle_text_command_async(update, context, rest)
    else:
        await update.message.reply_text(
            f"Unrecognised command: {command}",
            reply_markup=MAIN_MENU_KEYBOARD,
        )


async def handle_rating_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle numeric rating replies for papers."""
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    username = update.effective_user.username or "unknown"

    log_telegram_message_received(logger, str(chat_id), username, text)

    handled = await screening_bot.handle_rating_reply_async(update, context, text)
    if not handled:
        # Not a valid rating, show help
        await update.message.reply_text(
            "I didn't understand that. Use the menu buttons or type a command.",
            reply_markup=MAIN_MENU_KEYBOARD,
        )


async def periodic_tasks(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run periodic background tasks (called by job queue)."""
    try:
        react_to_minecraft_logs()
        run_daily_scan_if_due()
    except Exception as e:
        logger.error(f"Error in periodic tasks: {e}")


def main():
    print("Starting telegram bot...")
    init_swedish_db()
    init_screening_db()
    populate_db()

    app = Application.builder().token(get_telegram_bot_key()).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    # Swedish bot conversation handlers
    app.add_handler(swedish_bot.get_practice_conversation_handler())
    app.add_handler(swedish_bot.get_add_word_conversation_handler())

    # Button handlers for papers
    app.add_handler(MessageHandler(
        filters.Regex(r"^📚 Papers Status$"), handle_papers_status
    ))
    app.add_handler(MessageHandler(
        filters.Regex(r"^🔍 Scan Papers$"), handle_papers_scan
    ))

    # Help button
    app.add_handler(MessageHandler(
        filters.Regex(r"^❓ Help$"), help_command
    ))

    # Text command handlers (sv ..., papers ...)
    app.add_handler(MessageHandler(
        filters.Regex(r"(?i)^(sv|🇸🇪|papers)\s") & filters.TEXT,
        handle_text_command
    ))

    # Numeric replies for paper ratings
    app.add_handler(MessageHandler(
        filters.Regex(r"^\d{1,2}$") & filters.TEXT,
        handle_rating_reply
    ))

    # Fallback for unrecognized messages
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_rating_reply  # Will show help if not a valid rating
    ))

    # Schedule periodic tasks (minecraft logs, daily scans) - run every 60 seconds
    if app.job_queue:
        app.job_queue.run_repeating(periodic_tasks, interval=60, first=10)
    else:
        logger.warning("JobQueue not available - periodic tasks disabled. Install with: pip install 'python-telegram-bot[job-queue]'")

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
