#!/usr/bin/env python3
"""
Entrypoint for sending Telegram notifications.

Usage:
    python send_notification.py "Your message here"

Or import and use programmatically:
    from send_notification import notify
    notify("Task completed!")
"""
import sys
from telegram_bot.telegram_bot import send_message_to_me


def notify(message: str) -> None:
    """Send a notification message via Telegram."""
    send_message_to_me(message)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python send_notification.py <message>")
        sys.exit(1)

    message = " ".join(sys.argv[1:])
    notify(message)
