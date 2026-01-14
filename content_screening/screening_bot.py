"""
Telegram message handler for content screening ratings.
"""

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from content_screening.database import (
    init_db,
    get_oldest_pending_notification,
    get_article_by_id,
    insert_rating,
    mark_notification_rated,
    get_pending_notifications,
)
from util.logging_util import setup_logger

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


async def handle_status_async(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show status of pending notifications."""
    init_db()

    pending = get_pending_notifications()
    if not pending:
        await update.message.reply_text(
            "No articles awaiting rating.",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return

    count = len(pending)
    await update.message.reply_text(
        f"You have {count} article(s) awaiting rating.",
        reply_markup=MAIN_MENU_KEYBOARD,
    )

    oldest = pending[0]
    article = get_article_by_id(oldest.article_id)
    if article:
        await update.message.reply_text(
            f"Next: {article.title[:80]}...\n\nReply with a rating (1-10)",
            reply_markup=MAIN_MENU_KEYBOARD,
        )


async def handle_scan_async(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually trigger a scan."""
    from content_screening.scanner import run_arxiv_scan

    init_db()

    await update.message.reply_text(
        "Starting manual ArXiv scan...",
        reply_markup=MAIN_MENU_KEYBOARD,
    )

    try:
        total, new = run_arxiv_scan()
        await update.message.reply_text(
            f"Scan complete! Found {total} papers, {new} new interesting ones.",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
    except Exception as e:
        logger.error(f"Manual scan failed: {e}")
        await update.message.reply_text(
            f"Scan failed: {e}",
            reply_markup=MAIN_MENU_KEYBOARD,
        )


async def handle_rating_reply_async(
    update: Update, context: ContextTypes.DEFAULT_TYPE, message: str
) -> bool:
    """Handle a potential rating reply when there's a pending notification.

    Returns:
        True if the message was handled as a rating, False otherwise
    """
    init_db()

    pending = get_oldest_pending_notification()
    if pending is None:
        return False

    message = message.strip()
    try:
        rating = int(message)
    except ValueError:
        return False

    if not (1 <= rating <= 10):
        return False

    article = get_article_by_id(pending.article_id)
    if article is None:
        logger.error(f"Article {pending.article_id} not found for pending notification")
        mark_notification_rated(pending.id)
        return False

    insert_rating(pending.article_id, rating)
    mark_notification_rated(pending.id)
    logger.info(f"Recorded rating {rating} for article {article.external_id}")

    await update.message.reply_text(
        f"Thanks! Recorded rating {rating}/10 for: {article.title[:50]}...",
        reply_markup=MAIN_MENU_KEYBOARD,
    )

    remaining = len(get_pending_notifications())
    if remaining > 0:
        await update.message.reply_text(
            f"You have {remaining} more article(s) awaiting rating.",
            reply_markup=MAIN_MENU_KEYBOARD,
        )

    return True


async def handle_text_command_async(
    update: Update, context: ContextTypes.DEFAULT_TYPE, command: str
) -> None:
    """Handle text-based commands (papers status, papers scan, etc.)."""
    init_db()

    if not command.strip():
        await _show_help(update)
        return

    cmd = command.split()[0].lower()

    if cmd == "status":
        await handle_status_async(update, context)
    elif cmd == "scan":
        await handle_scan_async(update, context)
    else:
        await _show_help(update)


async def _show_help(update: Update) -> None:
    """Show help message."""
    await update.message.reply_text(
        """Papers commands:
papers status - Show pending articles awaiting rating
papers scan - Manually trigger a scan

Or use the menu buttons!""",
        reply_markup=MAIN_MENU_KEYBOARD,
    )
