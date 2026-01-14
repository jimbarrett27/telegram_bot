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


async def handle_scan_async(
    update: Update, context: ContextTypes.DEFAULT_TYPE, scan_type: str = "arxiv"
) -> None:
    """Manually trigger a scan.

    Args:
        update: Telegram update object
        context: Telegram context
        scan_type: "arxiv", "rss", or "all"
    """
    from content_screening.scanner import run_arxiv_scan, run_rss_scan

    init_db()

    results = []

    try:
        if scan_type in ("arxiv", "all"):
            await update.message.reply_text(
                "Starting ArXiv scan...",
                reply_markup=MAIN_MENU_KEYBOARD,
            )
            total, new = run_arxiv_scan()
            results.append(f"ArXiv: {total} found, {new} new")

        if scan_type in ("rss", "all"):
            await update.message.reply_text(
                "Starting RSS scan...",
                reply_markup=MAIN_MENU_KEYBOARD,
            )
            total, new = run_rss_scan()
            results.append(f"RSS: {total} found, {new} new")

        await update.message.reply_text(
            "Scan complete!\n" + "\n".join(results),
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

    parts = command.lower().split()
    cmd = parts[0]

    if cmd == "status":
        await handle_status_async(update, context)
    elif cmd == "scan":
        # Parse scan type from second argument (default to all)
        scan_type = parts[1] if len(parts) > 1 else "all"
        if scan_type not in ("arxiv", "rss", "all"):
            scan_type = "all"
        await handle_scan_async(update, context, scan_type)
    else:
        await _show_help(update)


async def _show_help(update: Update) -> None:
    """Show help message."""
    await update.message.reply_text(
        """Papers commands:
papers status - Show pending articles awaiting rating
papers scan - Scan all feeds (ArXiv + RSS)
papers scan arxiv - Scan only ArXiv
papers scan rss - Scan only RSS feeds

Or use the menu buttons!""",
        reply_markup=MAIN_MENU_KEYBOARD,
    )
