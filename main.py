import time
from telegram_bot.telegram_bot import get_telegram_updates, send_message

from minecraft.react_to_logs import react_to_logs as react_to_minecraft_logs
from swedish.database import init_db, populate_db
from swedish.swedish_bot import handle_message as handle_message_swedish

COMMAND_TO_MESSAGE_HANDLER = {
    "🇸🇪": handle_message_swedish,
    "sv": handle_message_swedish
}

def react_to_message(text: str, chat_id: str):
    
    command = text.split()[0]

    if command not in COMMAND_TO_MESSAGE_HANDLER:
        send_message(chat_id, f"Unrecognised command: {command}")
    else:
        command_to_send = (' '.join(text.split()[1:])).strip()
        COMMAND_TO_MESSAGE_HANDLER[command](command_to_send, chat_id)

def main():
    print("Starting telegram bot...")
    init_db()
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
                
                if text:
                    react_to_message(text, chat_id)
            
            react_to_minecraft_logs()

            # Sleep briefly to avoid hammering the API
            time.sleep(1)
            
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
