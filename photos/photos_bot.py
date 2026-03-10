from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from photos.email_sender import send_photo_email
from util.logging_util import setup_logger

logger = setup_logger(__name__)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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


def get_handlers():
    return [MessageHandler(filters.PHOTO, handle_photo)]
