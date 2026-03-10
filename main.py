import asyncio
import signal
from datetime import time as dt_time

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from gcp_util.secrets import get_swedish_bot_key, get_minecraft_bot_key, get_photos_bot_key, get_diary_bot_key, get_dnd_bot_key
from swedish.database import init_db as init_swedish_db, populate_db
from swedish import swedish_bot
from photos.photos_bot import get_handlers as get_photo_handlers
from diary.diary_bot import get_handlers as get_diary_handlers, schedule_jobs as schedule_diary_jobs
from dnd.database import init_db as init_dnd_db
from dnd.dnd_bot import get_handlers as get_dnd_handlers
from minecraft.react_to_logs import react_to_logs as react_to_minecraft_logs
from minecraft.healthcheck import run_healthcheck, run_on_demand_check, run_daily_summary
from telegram_bot.telegram_bot import TelegramBot
from util.logging_util import setup_logger, log_telegram_message_received

logger = setup_logger(__name__)


# --- Swedish bot handlers ---

async def swedish_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome! I can help you practise Swedish.",
        reply_markup=swedish_bot.MAIN_MENU_KEYBOARD,
    )


async def swedish_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """🇸🇪 Swedish Learning:
• 🇸🇪 Practise - Practice a random flashcard
• 📝 Add Word - Add a new word to your dictionary
• sv add <type> <word> - Add word directly (type: noun, verb, adj, auto)
• sv practise - Start practice directly"""
    await update.message.reply_text(help_text, reply_markup=swedish_bot.MAIN_MENU_KEYBOARD)


async def swedish_text_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    log_telegram_message_received(logger, str(update.effective_chat.id),
                                  update.effective_user.username or "unknown", text)
    rest = ' '.join(text.split()[1:]).strip()
    await swedish_bot.handle_text_command_async(update, context, rest)


async def swedish_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_telegram_message_received(logger, str(update.effective_chat.id),
                                  update.effective_user.username or "unknown",
                                  update.message.text)
    await update.message.reply_text(
        "I didn't understand that. Use the menu buttons or type 'sv help'.",
        reply_markup=swedish_bot.MAIN_MENU_KEYBOARD,
    )


# --- Minecraft bot handlers ---

async def minecraft_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Minecraft server monitor bot.\n\n"
        "Use /status to check server health.",
    )


async def minecraft_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """Available commands:

🖥️ Minecraft Server:
• /status - Check server & tunnel health
• Automatic alerts when server state changes
• Daily summary at 10am"""
    await update.message.reply_text(help_text)


async def minecraft_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_telegram_message_received(logger, str(update.effective_chat.id),
                                  update.effective_user.username or "unknown",
                                  update.message.text)
    await update.message.reply_text("Checking server status...")
    msg = run_on_demand_check()
    await update.message.reply_text(msg)


async def periodic_tasks(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        react_to_minecraft_logs(context.bot_data["minecraft_bot"])
    except Exception as e:
        logger.error(f"Error in periodic tasks: {e}")


async def healthcheck_task(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        run_healthcheck(context.bot_data["minecraft_bot"])
    except Exception as e:
        logger.error(f"Error in healthcheck: {e}")


async def daily_summary_task(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        run_daily_summary(context.bot_data["minecraft_bot"])
    except Exception as e:
        logger.error(f"Error in daily summary: {e}")


# --- App setup ---

def build_swedish_app() -> Application:
    app = Application.builder().token(get_swedish_bot_key()).build()

    app.add_handler(CommandHandler("start", swedish_start))
    app.add_handler(CommandHandler("help", swedish_help))
    app.add_handler(swedish_bot.get_practice_conversation_handler())
    app.add_handler(swedish_bot.get_add_word_conversation_handler())
    app.add_handler(MessageHandler(
        filters.Regex(r"^❓ Help$"), swedish_help
    ))
    app.add_handler(MessageHandler(
        filters.Regex(r"(?i)^(sv|🇸🇪)\s") & filters.TEXT,
        swedish_text_command,
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        swedish_fallback,
    ))

    return app


def build_diary_app() -> Application:
    app = Application.builder().token(get_diary_bot_key()).build()
    for handler in get_diary_handlers():
        app.add_handler(handler)
    if app.job_queue:
        schedule_diary_jobs(app.job_queue)
    else:
        logger.warning("JobQueue not available - diary prompts disabled.")
    return app


def build_dnd_app() -> Application:
    app = Application.builder().token(get_dnd_bot_key()).build()
    for handler in get_dnd_handlers():
        app.add_handler(handler)
    return app


def build_photos_app() -> Application:
    app = Application.builder().token(get_photos_bot_key()).build()
    for handler in get_photo_handlers():
        app.add_handler(handler)
    return app


def build_minecraft_app() -> Application:
    app = Application.builder().token(get_minecraft_bot_key()).build()
    app.bot_data["minecraft_bot"] = TelegramBot(get_minecraft_bot_key())

    app.add_handler(CommandHandler("start", minecraft_start))
    app.add_handler(CommandHandler("help", minecraft_help))
    app.add_handler(CommandHandler("status", minecraft_status))

    if app.job_queue:
        app.job_queue.run_repeating(periodic_tasks, interval=60, first=10)
        app.job_queue.run_repeating(healthcheck_task, interval=300, first=30)
        app.job_queue.run_daily(daily_summary_task, time=dt_time(hour=10, minute=0))
    else:
        logger.warning("JobQueue not available - periodic tasks disabled.")

    return app


async def run():
    swedish_app = build_swedish_app()
    minecraft_app = build_minecraft_app()
    photos_app = build_photos_app()
    diary_app = build_diary_app()
    dnd_app = build_dnd_app()

    async with swedish_app, minecraft_app, photos_app, diary_app, dnd_app:
        await swedish_app.start()
        await swedish_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await minecraft_app.start()
        await minecraft_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await photos_app.start()
        await photos_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await diary_app.start()
        await diary_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await dnd_app.start()
        await dnd_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

        logger.info("All bots are running.")
        print("All bots are running...")

        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        await stop_event.wait()

        print("Shutting down...")
        await swedish_app.updater.stop()
        await swedish_app.stop()
        await minecraft_app.updater.stop()
        await minecraft_app.stop()
        await photos_app.updater.stop()
        await photos_app.stop()
        await diary_app.updater.stop()
        await diary_app.stop()
        await dnd_app.updater.stop()
        await dnd_app.stop()


def main():
    print("Starting telegram bots...")
    init_swedish_db()
    init_dnd_db()
    populate_db()
    asyncio.run(run())


if __name__ == "__main__":
    main()
