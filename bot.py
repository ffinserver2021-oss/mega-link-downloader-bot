import asyncio
import os
import logging

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Environment variables সরাসরি লোড করা
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", os.environ.get("BOT_TOKEN", ""))
APP_ID = int(os.environ.get("APP_ID", os.environ.get("API_ID", 0)))
API_HASH = os.environ.get("API_HASH", "")

DOWNLOAD_LOCATION = os.environ.get("DOWNLOAD_LOCATION", "./DOWNLOADS")
ADMIN_LOCATION = os.environ.get("ADMIN_LOCATION", "./plugins")
CREDENTIALS_LOCATION = os.environ.get("CREDENTIALS_LOCATION", "./credentials")

import pyrogram

if __name__ == "__main__":
    os.makedirs(DOWNLOAD_LOCATION, exist_ok=True)
    os.makedirs(ADMIN_LOCATION, exist_ok=True)
    os.makedirs(CREDENTIALS_LOCATION, exist_ok=True)

    app = pyrogram.Client(
        "Mega_Link_Downloader_Bot",
        bot_token=TG_BOT_TOKEN,
        api_id=APP_ID,
        api_hash=API_HASH,
        plugins=dict(root="plugins")
    )
    app.run()
