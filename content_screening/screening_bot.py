"""
Telegram message handler for content screening ratings.
"""

from telegram_bot.telegram_bot import send_message, send_message_to_me
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


def handle_message(message: str, chat_id: str):
    """Handle a 'papers' prefixed message.

    Subcommands:
        status - Show pending articles awaiting rating
        scan - Manually trigger a scan
        <anything else> - Show help
    """
    init_db()

    if not message.strip():
        _show_help(chat_id)
        return

    command = message.split()[0].lower()

    if command == "status":
        _handle_status(chat_id)
    elif command == "scan":
        _handle_manual_scan(chat_id)
    else:
        _show_help(chat_id)


def handle_rating_reply(message: str, chat_id: str) -> bool:
    """Handle a potential rating reply when there's a pending notification.

    This should be called BEFORE command routing in main.py.
    If there's a pending notification and the message is a number 1-10,
    this will record the rating.

    Args:
        message: The incoming message text
        chat_id: The chat ID

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

    send_message(chat_id, f"Thanks! Recorded rating {rating}/10 for: {article.title[:50]}...")

    remaining = len(get_pending_notifications())
    if remaining > 0:
        send_message(chat_id, f"You have {remaining} more article(s) awaiting rating.")

    return True


def _show_help(chat_id: str):
    """Show help message."""
    send_message(chat_id, """Papers commands:
papers status - Show pending articles awaiting rating
papers scan - Manually trigger a scan""")


def _handle_status(chat_id: str):
    """Show status of pending notifications."""
    pending = get_pending_notifications()
    if not pending:
        send_message(chat_id, "No articles awaiting rating.")
        return

    count = len(pending)
    send_message(chat_id, f"You have {count} article(s) awaiting rating.")

    oldest = pending[0]
    article = get_article_by_id(oldest.article_id)
    if article:
        send_message(chat_id, f"Next: {article.title[:80]}...\n\nReply with a rating (1-10)")


def _handle_manual_scan(chat_id: str):
    """Manually trigger a scan."""
    from content_screening.scanner import run_arxiv_scan

    send_message(chat_id, "Starting manual ArXiv scan...")

    try:
        total, new = run_arxiv_scan()
        send_message(chat_id, f"Scan complete! Found {total} papers, {new} new interesting ones.")
    except Exception as e:
        logger.error(f"Manual scan failed: {e}")
        send_message(chat_id, f"Scan failed: {e}")
