
import time
from telegram_bot.telegram_bot import get_telegram_updates, send_message

from minecraft.react_to_logs import react_to_logs

def main():
    print("Starting telegram bot...")
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
                    print(f"Received from {chat_id}: {text}")
                    send_message(chat_id, text)
            
            react_to_logs()

            # Sleep briefly to avoid hammering the API
            time.sleep(1)
            
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
