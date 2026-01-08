import sqlite3
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

DB_NAME = "claude_messages.db"


class MessageDirection(Enum):
    OUTGOING = "outgoing"  # From Claude to user
    INCOMING = "incoming"  # From user to Claude


class MessageStatus(Enum):
    PENDING = "pending"    # Waiting to be sent
    SENT = "sent"          # Sent to Telegram
    RECEIVED = "received"  # Reply received, waiting to be read
    READ = "read"          # Reply has been read by Claude


@dataclass
class Message:
    id: int
    conversation_id: str
    direction: MessageDirection
    content: str
    status: MessageStatus
    created_at: int  # epoch timestamp
    processed_at: Optional[int]  # epoch timestamp


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                direction TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                processed_at INTEGER
            )
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_conversation_id
            ON messages(conversation_id)
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_status_direction
            ON messages(status, direction)
        ''')
    conn.close()


def _row_to_message(row) -> Message:
    return Message(
        id=row['id'],
        conversation_id=row['conversation_id'],
        direction=MessageDirection(row['direction']),
        content=row['content'],
        status=MessageStatus(row['status']),
        created_at=row['created_at'],
        processed_at=row['processed_at']
    )


def create_outgoing_message(content: str, conversation_id: Optional[str] = None) -> str:
    """Create a new outgoing message from Claude to user.

    Returns the conversation_id.
    """
    if conversation_id is None:
        conversation_id = str(uuid.uuid4())

    conn = get_db_connection()
    with conn:
        conn.execute('''
            INSERT INTO messages (conversation_id, direction, content, status, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            conversation_id,
            MessageDirection.OUTGOING.value,
            content,
            MessageStatus.PENDING.value,
            int(time.time())
        ))
    conn.close()
    return conversation_id


def mark_message_sent(message_id: int):
    """Mark an outgoing message as sent."""
    conn = get_db_connection()
    with conn:
        conn.execute('''
            UPDATE messages
            SET status = ?, processed_at = ?
            WHERE id = ?
        ''', (MessageStatus.SENT.value, int(time.time()), message_id))
    conn.close()


def create_incoming_message(content: str, conversation_id: str) -> int:
    """Create an incoming message (reply from user).

    Returns the message id.
    """
    conn = get_db_connection()
    with conn:
        cursor = conn.execute('''
            INSERT INTO messages (conversation_id, direction, content, status, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            conversation_id,
            MessageDirection.INCOMING.value,
            content,
            MessageStatus.RECEIVED.value,
            int(time.time())
        ))
        message_id = cursor.lastrowid
    conn.close()
    return message_id


def get_pending_outgoing() -> List[Message]:
    """Get all outgoing messages waiting to be sent."""
    conn = get_db_connection()
    cursor = conn.execute('''
        SELECT * FROM messages
        WHERE direction = ? AND status = ?
        ORDER BY created_at ASC
    ''', (MessageDirection.OUTGOING.value, MessageStatus.PENDING.value))
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_message(row) for row in rows]


def get_unread_incoming(conversation_id: str) -> List[Message]:
    """Get all unread incoming messages for a conversation."""
    conn = get_db_connection()
    cursor = conn.execute('''
        SELECT * FROM messages
        WHERE conversation_id = ? AND direction = ? AND status = ?
        ORDER BY created_at ASC
    ''', (conversation_id, MessageDirection.INCOMING.value, MessageStatus.RECEIVED.value))
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_message(row) for row in rows]


def mark_message_read(message_id: int):
    """Mark an incoming message as read."""
    conn = get_db_connection()
    with conn:
        conn.execute('''
            UPDATE messages
            SET status = ?, processed_at = ?
            WHERE id = ?
        ''', (MessageStatus.READ.value, int(time.time()), message_id))
    conn.close()


def get_latest_sent_conversation() -> Optional[str]:
    """Get the conversation_id of the most recent sent (awaiting reply) message."""
    conn = get_db_connection()
    cursor = conn.execute('''
        SELECT conversation_id FROM messages
        WHERE direction = ? AND status = ?
        ORDER BY created_at DESC
        LIMIT 1
    ''', (MessageDirection.OUTGOING.value, MessageStatus.SENT.value))
    row = cursor.fetchone()
    conn.close()
    return row['conversation_id'] if row else None


def has_pending_conversation() -> bool:
    """Check if there's any outgoing message awaiting a reply.

    Returns False if the conversation already has a reply (even if unread).
    """
    conversation_id = get_latest_sent_conversation()
    if conversation_id is None:
        return False

    # Check if there's already a reply for this conversation
    conn = get_db_connection()
    cursor = conn.execute('''
        SELECT COUNT(*) FROM messages
        WHERE conversation_id = ? AND direction = ?
    ''', (conversation_id, MessageDirection.INCOMING.value))
    count = cursor.fetchone()[0]
    conn.close()

    # Only pending if there's no reply yet
    return count == 0


def get_conversation_messages(conversation_id: str) -> List[Message]:
    """Get all messages in a conversation."""
    conn = get_db_connection()
    cursor = conn.execute('''
        SELECT * FROM messages
        WHERE conversation_id = ?
        ORDER BY created_at ASC
    ''', (conversation_id,))
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_message(row) for row in rows]


def clear_all_pending_conversations() -> int:
    """Clear all pending conversations by marking sent messages as read.

    This is a failsafe to reset the bot to a clean state.

    Returns the number of conversations cleared.
    """
    conn = get_db_connection()
    with conn:
        cursor = conn.execute('''
            UPDATE messages
            SET status = ?, processed_at = ?
            WHERE direction = ? AND status = ?
        ''', (
            MessageStatus.READ.value,
            int(time.time()),
            MessageDirection.OUTGOING.value,
            MessageStatus.SENT.value
        ))
        count = cursor.rowcount
    conn.close()
    return count
