import requests
from gcp_util.secrets import get_telegram_bot_key, get_telegram_user_id


def send_message_to_me(message: str):
    """
    Sends a message to me from my bot
    """

    response_data = {"chat_id": get_telegram_user_id(), "text": message}

    print(response_data)

    requests.post(
        f"https://api.telegram.org/bot{get_telegram_bot_key()}/sendMessage",
        json=response_data,
        timeout=1,
    )