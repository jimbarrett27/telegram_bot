"""Client API for Claude to send and receive Telegram messages."""

import time
from typing import Optional

from claude.database import (
    create_outgoing_message,
    get_unread_incoming,
    mark_message_read,
    init_db,
)


def send_message(message: str, conversation_id: Optional[str] = None) -> str:
    """Queue a message to be sent to the user via Telegram.

    Args:
        message: The message content to send
        conversation_id: Optional existing conversation to continue

    Returns:
        The conversation_id for tracking replies
    """
    init_db()
    return create_outgoing_message(message, conversation_id)


def wait_for_reply(conversation_id: str, timeout: int = 300, poll_interval: float = 1.0) -> Optional[str]:
    """Wait for a reply to a conversation.

    Args:
        conversation_id: The conversation to wait for a reply on
        timeout: Maximum seconds to wait (default 5 minutes)
        poll_interval: Seconds between checks (default 1 second)

    Returns:
        The reply content, or None if timeout reached
    """
    init_db()
    start_time = time.time()

    while time.time() - start_time < timeout:
        replies = get_unread_incoming(conversation_id)
        if replies:
            # Get the first unread reply
            reply = replies[0]
            mark_message_read(reply.id)
            return reply.content

        time.sleep(poll_interval)

    return None


def send_and_wait(message: str, timeout: int = 300) -> Optional[str]:
    """Send a message and wait for a reply.

    This is a convenience method combining send_message and wait_for_reply.

    Args:
        message: The message to send
        timeout: Maximum seconds to wait for reply

    Returns:
        The reply content, or None if timeout reached
    """
    conversation_id = send_message(message)
    return wait_for_reply(conversation_id, timeout)


def notify(message: str) -> str:
    """Send a notification message without waiting for a reply.

    This is a fire-and-forget message - Claude won't wait for a response.

    Args:
        message: The notification message

    Returns:
        The conversation_id (though typically not needed for notifications)
    """
    return send_message(message)
