import requests
from gcp_util.secrets import get_telegram_user_id
from util.logging_util import setup_logger, log_telegram_message_sent

logger = setup_logger(__name__)


class TelegramBot:
    def __init__(self, token: str):
        self._api_url = f"https://api.telegram.org/bot{token}"
        self._my_user_id = get_telegram_user_id()

    def send_message(self, chat_id: int, message: str):
        response_data = {"chat_id": chat_id, "text": message}
        log_telegram_message_sent(logger, str(chat_id), message)
        requests.post(f"{self._api_url}/sendMessage", json=response_data)

    def send_message_to_me(self, message: str):
        print(message)
        self.send_message(self._my_user_id, message)

    def get_updates(self, offset: int = 0) -> list[dict]:
        resp_json = requests.get(
            f"{self._api_url}/getUpdates", json={"offset": offset}
        ).json()
        return resp_json.get("result", [])
