from datetime import timedelta

from telegram import Update
from telegram.ext import ContextTypes, JobQueue, MessageHandler, filters

from diary.storage import entry_exists, save_entry
from gcp_util.secrets import get_telegram_user_id
from util.logging_util import setup_logger
from util.timezone import stockholm_now, stockholm_time

logger = setup_logger(__name__)

EVENING_PROMPT = "How was your day? 📖"
MORNING_PROMPT = "You didn't write yesterday — what did you get up to? 📖"
FLUSH_DELAY_SECONDS = 15 * 60


async def send_evening_prompt(context: ContextTypes.DEFAULT_TYPE) -> None:
    today = stockholm_now().date()
    if not entry_exists(today):
        context.bot_data["prompt_date"] = today
        await context.bot.send_message(get_telegram_user_id(), EVENING_PROMPT)


async def send_morning_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    yesterday = (stockholm_now() - timedelta(days=1)).date()
    if not entry_exists(yesterday):
        context.bot_data["prompt_date"] = yesterday
        await context.bot.send_message(get_telegram_user_id(), MORNING_PROMPT)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text

    if "diary_buffer" not in context.bot_data:
        context.bot_data["diary_buffer"] = []
        context.bot_data["diary_chat_id"] = update.effective_chat.id
        context.bot_data["diary_date"] = context.bot_data.pop("prompt_date", stockholm_now().date())

    context.bot_data["diary_buffer"].append(text)

    if existing_job := context.bot_data.get("diary_flush_job"):
        existing_job.schedule_removal()

    context.bot_data["diary_flush_job"] = context.job_queue.run_once(
        flush_entry, FLUSH_DELAY_SECONDS
    )


async def flush_entry(context: ContextTypes.DEFAULT_TYPE) -> None:
    buffer = context.bot_data.pop("diary_buffer", [])
    entry_date = context.bot_data.pop("diary_date", stockholm_now().date())
    chat_id = context.bot_data.pop("diary_chat_id", get_telegram_user_id())
    context.bot_data.pop("diary_flush_job", None)

    if not buffer:
        return

    save_entry(entry_date, "\n\n".join(buffer))
    await context.bot.send_message(chat_id, "Entry saved! 📖")


def get_handlers():
    return [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)]


def schedule_jobs(job_queue: JobQueue) -> None:
    job_queue.run_daily(send_evening_prompt, time=stockholm_time(20))
    job_queue.run_daily(send_morning_reminder, time=stockholm_time(8))
