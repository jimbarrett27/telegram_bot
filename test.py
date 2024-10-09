import requests
from gcp_util.secrets import get_telegram_secret_token, get_telegram_bot_key
from time import sleep


requests.post(
    f"https://europe-west1-personal-website-318015.cloudfunctions.net/telegram_bot",
    json={
        "X-Telegram-Bot-Api-Secret-Token": get_telegram_secret_token()
    }
)

sleep(3)

resp =requests.get(f'https://api.telegram.org/bot{get_telegram_bot_key()}/getWebhookInfo')

print(resp.content)