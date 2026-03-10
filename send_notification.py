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
from gcp_util.secrets import get_minecraft_bot_key
from telegram_bot.telegram_bot import TelegramBot


def notify(message: str) -> None:
    """Send a notification message via Telegram."""
    bot = TelegramBot(get_minecraft_bot_key())
    bot.send_message_to_me(message)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python send_notification.py <message>")
        sys.exit(1)

    message = " ".join(sys.argv[1:])
    notify(message)
