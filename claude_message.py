#!/usr/bin/env python3
"""
Entrypoint for Claude to send Telegram messages and wait for replies.

Usage:
    # Send a message and wait for reply (default 5 minute timeout)
    uv run python claude_message.py "Your question here"

    # Send a notification without waiting for reply
    uv run python claude_message.py --notify "Task completed!"

    # Wait for reply with custom timeout (in seconds)
    uv run python claude_message.py --timeout 600 "Your question here"

    # Wait for reply to an existing conversation
    uv run python claude_message.py --wait <conversation_id>
"""
import argparse
import sys

from claude.client import send_and_wait, notify, wait_for_reply


def main():
    parser = argparse.ArgumentParser(
        description="Send messages to user via Telegram and optionally wait for replies"
    )
    parser.add_argument(
        "message",
        nargs="*",
        help="The message to send"
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Send notification only (don't wait for reply)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout in seconds to wait for reply (default: 300)"
    )
    parser.add_argument(
        "--wait",
        metavar="CONVERSATION_ID",
        help="Wait for reply to an existing conversation"
    )

    args = parser.parse_args()

    # Handle --wait flag (waiting for existing conversation)
    if args.wait:
        print(f"Waiting for reply to conversation {args.wait}...", file=sys.stderr)
        reply = wait_for_reply(args.wait, timeout=args.timeout)
        if reply:
            print(reply)
            sys.exit(0)
        else:
            print("Timeout waiting for reply", file=sys.stderr)
            sys.exit(1)

    # Build message from arguments
    message = " ".join(args.message)
    if not message:
        parser.print_help()
        sys.exit(1)

    if args.notify:
        # Fire-and-forget notification
        conversation_id = notify(message)
        print(f"Notification sent (conversation: {conversation_id})", file=sys.stderr)
        sys.exit(0)
    else:
        # Send and wait for reply
        print(f"Sending message and waiting for reply (timeout: {args.timeout}s)...", file=sys.stderr)
        reply = send_and_wait(message, timeout=args.timeout)
        if reply:
            print(reply)
            sys.exit(0)
        else:
            print("Timeout waiting for reply", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
