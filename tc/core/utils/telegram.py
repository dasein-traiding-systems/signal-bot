import asyncio
from core.base import CoreBase
from core.types import RestMethod
import logging
from urllib.parse import quote
from config import Config

CHANNEL_ID = "-1001734167495"
# CHANNEL_ID = "-869981089"

TELEGRAM_API_SEND_MESSAGE_URL = 'https://api.telegram.org/bot{apiToken}/sendMessage'
TELEGRAM_API_GET_UPDATES_URL = 'https://api.telegram.org/bot{apiToken}/getUpdates'


async def get_telegram_chat_updates():
    content, _ = await CoreBase.get_request().request_json(url=TELEGRAM_API_GET_UPDATES_URL.format(
        apiToken= Config.TELEGRAM_BOT_TOKEN),
        method=RestMethod.POST)
    print(content)


async def send_to_telegram(message: str, channel_id: str = CHANNEL_ID):
    try:
        content, _ = await CoreBase.get_request().request_json(url=TELEGRAM_API_SEND_MESSAGE_URL.format(
            apiToken= Config.TELEGRAM_BOT_TOKEN),
            method=RestMethod.POST,
            params={'chat_id': quote(channel_id), 'text': message, 'parse_mode': 'html'})
    except Exception as e:
        logging.error(f"Telegram error {e}")


if __name__ == "__main__":
    asyncio.run(get_telegram_chat_updates())

    asyncio.run(send_to_telegram("test!"))
    asyncio.run(CoreBase.close())

