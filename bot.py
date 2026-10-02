import asyncio

# Fix for event loop issues in newer Python versions
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import os

# the secret configuration specific things
if bool(os.environ.get("WEBHOOK", False)):
    from sample_config import Config
else:
    from config import Config

# Ensure required directory configs exist with defaults if missing
if not hasattr(Config, "DOWNLOAD_LOCATION"):
    setattr(Config, "DOWNLOAD_LOCATION", os.environ.get("DOWNLOAD_LOCATION", "./DOWNLOADS"))
if not hasattr(Config, "ADMIN_LOCATION"):
    setattr(Config, "ADMIN_LOCATION", os.environ.get("ADMIN_LOCATION", "./plugins"))
if not hasattr(Config, "CREDENTIALS_LOCATION"):
    setattr(Config, "CREDENTIALS_LOCATION", os.environ.get("CREDENTIALS_LOCATION", "./credentials"))

import pyrogram
logging.getLogger("pyrogram").setLevel(logging.WARNING)
from pyrogram import Client, idle

if __name__ == "__main__":
    # Creating essential directories, if they do not exist
    if not os.path.isdir(Config.DOWNLOAD_LOCATION):
        os.makedirs(Config.DOWNLOAD_LOCATION, exist_ok=True)
    if not os.path.isdir(Config.ADMIN_LOCATION):
        os.makedirs(Config.ADMIN_LOCATION, exist_ok=True)
    if not os.path.isdir(Config.CREDENTIALS_LOCATION):
        os.makedirs(Config.CREDENTIALS_LOCATION, exist_ok=True)
        
    plugins = dict(
        root="plugins"
    )
    app = pyrogram.Client(
        "Mega_Link_Downloader_Bot",
        bot_token=Config.TG_BOT_TOKEN,
        api_id=Config.APP_ID,
        api_hash=Config.API_HASH,
        plugins=plugins
    )
    app.run()
