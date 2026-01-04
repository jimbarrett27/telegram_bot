import requests
from gcp_util.secrets import get_telegram_bot_key, get_telegram_user_id
from functools import lru_cache
from util.logging_util import setup_logger, log_telegram_message_sent

logger = setup_logger(__name__)

@lru_cache
def get_telegram_api_url() -> str:

    return f"https://api.telegram.org/bot{get_telegram_bot_key()}"




def send_message(chat_id: int, message: str):
    """
    Sends a message to a specific chat_id
    """
    api_url = get_telegram_api_url()
    response_data = {"chat_id": chat_id, "text": message}
    
    # Log the outgoing message
    log_telegram_message_sent(logger, str(chat_id), message)
    
    requests.post(
        f"{api_url}/sendMessage",
        json=response_data,
    )

def send_message_to_me(message: str):
    """
    Sends a message to me from my bot
    """
    print(message)
    send_message(get_telegram_user_id(), message)

def get_telegram_updates(offset: int = 0) -> list[dict]:
    """
    Fetches the raw updates from telegram
    """
    api_url = get_telegram_api_url()
    resp_json = requests.get(f"{api_url}/getUpdates", json={'offset': offset}).json()
    
    # Check if 'result' is in the response, if not return empty list
    return resp_json.get('result', [])
    