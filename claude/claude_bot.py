"""Telegram message handler for Claude communication."""

from telegram_bot.telegram_bot import send_message, send_message_to_me
from claude.database import (
    init_db,
    get_pending_outgoing,
    mark_message_sent,
    create_incoming_message,
    get_latest_sent_conversation,
    has_pending_conversation,
    clear_all_pending_conversations,
)
from util.logging_util import setup_logger

logger = setup_logger(__name__)


def handle_message(message: str, chat_id: str):
    """Handle an 'ai' prefixed message or a direct reply.

    Subcommands:
        status - Show if there are pending conversations
        reset - Clear all pending conversations (failsafe)
        <anything else> - Treat as reply to most recent outgoing message
    """
    init_db()

    if not message.strip():
        send_message(chat_id, "Usage: ai <reply> or ai status or ai reset")
        return

    command = message.split()[0].lower()

    if command == "status":
        _handle_status(chat_id)
    elif command == "reset":
        _handle_reset(chat_id)
    else:
        # Treat entire message as a reply
        _handle_reply(message, chat_id)


def handle_auto_reply(message: str, chat_id: str) -> bool:
    """Handle a potential auto-reply when there's a pending conversation.

    This should be called BEFORE command routing in main.py.
    If there's a pending outgoing message awaiting reply, this will
    capture the message as a reply.

    Args:
        message: The incoming message text
        chat_id: The chat ID

    Returns:
        True if the message was handled as an auto-reply, False otherwise
    """
    init_db()

    if not has_pending_conversation():
        return False

    conversation_id = get_latest_sent_conversation()
    if conversation_id:
        create_incoming_message(message, conversation_id)
        logger.info(f"Auto-captured reply for conversation {conversation_id}")
        send_message(chat_id, "Got it, passing your reply to Claude.")
        return True

    return False


def process_outgoing_messages():
    """Process any pending outgoing messages from Claude.

    This should be called from the main loop, similar to react_to_minecraft_logs().
    """
    init_db()

    pending = get_pending_outgoing()
    for msg in pending:
        try:
            # Send to user via Telegram
            send_message_to_me(f"[Claude] {msg.content}")
            mark_message_sent(msg.id)
            logger.info(f"Sent Claude message {msg.id} for conversation {msg.conversation_id}")
        except Exception as e:
            logger.error(f"Failed to send Claude message {msg.id}: {e}")


def _handle_status(chat_id: str):
    """Show status of pending conversations."""
    if has_pending_conversation():
        conv_id = get_latest_sent_conversation()
        send_message(chat_id, f"Waiting for reply on conversation: {conv_id[:8]}...")
    else:
        send_message(chat_id, "No pending conversations from Claude.")


def _handle_reply(message: str, chat_id: str):
    """Handle a reply to a pending conversation."""
    conversation_id = get_latest_sent_conversation()

    if not conversation_id:
        send_message(chat_id, "No pending conversation from Claude to reply to.")
        return

    create_incoming_message(message, conversation_id)
    logger.info(f"Received reply for conversation {conversation_id}")
    send_message(chat_id, f"Reply recorded for conversation {conversation_id[:8]}...")


def _handle_reset(chat_id: str):
    """Clear all pending conversations as a failsafe."""
    count = clear_all_pending_conversations()
    if count > 0:
        logger.info(f"Reset: cleared {count} pending conversation(s)")
        send_message(chat_id, f"Reset complete. Cleared {count} pending conversation(s).")
    else:
        send_message(chat_id, "No pending conversations to clear.")
