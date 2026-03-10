from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from gcp_util.secrets import get_telegram_user_id, get_photos_allowed_user_ids
from photos.email_sender import send_photo_email
from util.logging_util import setup_logger

logger = setup_logger(__name__)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed = [get_telegram_user_id()] + get_photos_allowed_user_ids()
    if update.effective_user.id not in allowed:
        await update.message.reply_text("Unauthorised.")
        return

    photo = update.message.photo[-1]  # highest resolution
    await update.message.reply_text("Sending to photo frame...")

    try:
        file = await context.bot.get_file(photo.file_id)
        image_bytes = bytes(await file.download_as_bytearray())
        send_photo_email(image_bytes, f"{photo.file_unique_id}.jpg")
        await update.message.reply_text("Done! Photo sent to the frame.")
    except Exception as e:
        logger.error(f"Failed to send photo: {e}")
        await update.message.reply_text(f"Failed to send photo: {e}")


async def handle_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Your Telegram user ID is: `{update.effective_user.id}`", parse_mode="Markdown")


def get_handlers():
    return [
        CommandHandler("id", handle_id),
        MessageHandler(filters.PHOTO, handle_photo),
    ]
