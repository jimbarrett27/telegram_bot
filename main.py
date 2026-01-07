import time
from telegram_bot.telegram_bot import get_telegram_updates, send_message

from minecraft.react_to_logs import react_to_logs as react_to_minecraft_logs
from swedish.database import init_db as init_swedish_db, populate_db
from swedish.swedish_bot import handle_message as handle_message_swedish
from claude.database import init_db as init_claude_db
from claude.claude_bot import (
    handle_message as handle_message_claude,
    handle_auto_reply,
    process_outgoing_messages as process_claude_outgoing_messages,
)
from util.logging_util import setup_logger, log_telegram_message_received

logger = setup_logger(__name__)

COMMAND_TO_MESSAGE_HANDLER = {
    "🇸🇪": handle_message_swedish,
    "sv": handle_message_swedish,
    "ai": handle_message_claude,
}

def react_to_message(text: str, chat_id: str):
    # Auto-detect: if Claude is waiting for a reply, capture any message as a reply
    # (unless it's explicitly an "ai" command)
    command = text.split()[0]
    if command != "ai" and handle_auto_reply(text, chat_id):
        return

    if command not in COMMAND_TO_MESSAGE_HANDLER:
        send_message(chat_id, f"Unrecognised command: {command}")
    else:
        command_to_send = (' '.join(text.split()[1:])).strip()
        COMMAND_TO_MESSAGE_HANDLER[command](command_to_send, chat_id)

def main():
    print("Starting telegram bot...")
    init_swedish_db()
    init_claude_db()
    populate_db()
    offset = 0
  
    while True:
        try:
            updates = get_telegram_updates(offset)
            
            for update in updates:
                update_id = update['update_id']
                
                # Advance offset so we don't handle this message again
                offset = update_id + 1
                
                message = update.get('message')
                if not message:
                    continue
                    
                chat_id = message['chat']['id']
                text = message.get('text')
                username = message.get('from', {}).get('username', 'unknown')
                
                if text:
                    # Log incoming message
                    log_telegram_message_received(logger, str(chat_id), username, text)
                    react_to_message(text, chat_id)
            
            react_to_minecraft_logs()
            process_claude_outgoing_messages()

            # Sleep briefly to avoid hammering the API
            time.sleep(1)
            
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
