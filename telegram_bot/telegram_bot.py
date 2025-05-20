import requests
from gcp_util.secrets import get_telegram_bot_key, get_telegram_user_id
from functools import lru_cache

@lru_cache
def get_telegram_api_url() -> str:

    return f"https://api.telegram.org/bot{get_telegram_bot_key()}"



def send_message_to_me(message: str):
    """
    Sends a message to me from my bot
    """

    response_data = {"chat_id": get_telegram_user_id(), "text": message}

    print(message)

    api_url = get_telegram_api_url()

    requests.post(
        f" {api_url}/sendMessage",
        json=response_data,
    )

def fetch_messages(offset: int = 0) -> list[str]:

    api_url = get_telegram_api_url()

    resp_json = requests.get(f"{api_url}/getUpdates", json={'offset': offset}).json()

    return [r['message']['text'] for r in resp_json['result']]
    