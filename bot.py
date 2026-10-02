import asyncio
import os
import sys
import logging

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Dummy In-Memory Redis to bypass localhost:6379 error
class MockRedis:
    def __init__(self, *args, **kwargs):
        self.store = {}
    def ping(self):
        return True
    def set(self, name, value, *args, **kwargs):
        self.store[name] = value
        return True
    def get(self, name):
        return self.store.get(name)
    def delete(self, *names):
        for n in names:
            self.store.pop(n, None)
        return True
    def smembers(self, name):
        return self.store.get(name, set())
    def sadd(self, name, *values):
        s = self.store.setdefault(name, set())
        for v in values:
            s.add(str(v).encode() if isinstance(v, str) else v)
        return True
    def srem(self, name, *values):
        s = self.store.setdefault(name, set())
        for v in values:
            s.discard(str(v).encode() if isinstance(v, str) else v)
        return True
    def sismember(self, name, value):
        s = self.store.get(name, set())
        val = str(value).encode() if isinstance(value, str) else value
        return val in s

import redis
redis.Redis = MockRedis
redis.StrictRedis = MockRedis

# Load config class or create dummy
try:
    if bool(os.environ.get("WEBHOOK", False)):
        from sample_config import Config
    else:
        from config import Config
except ImportError:
    class Config:
        pass

defaults = {
    "TG_BOT_TOKEN": os.environ.get("TG_BOT_TOKEN", os.environ.get("BOT_TOKEN", "")),
    "APP_ID": int(os.environ.get("APP_ID", os.environ.get("API_ID", 0))),
    "API_HASH": os.environ.get("API_HASH", ""),
    "DOWNLOAD_LOCATION": os.environ.get("DOWNLOAD_LOCATION", "./DOWNLOADS"),
    "ADMIN_LOCATION": os.environ.get("ADMIN_LOCATION", "./plugins"),
    "CREDENTIALS_LOCATION": os.environ.get("CREDENTIALS_LOCATION", "./credentials"),
    "AUTH_USERS": set(int(x) for x in os.environ.get("AUTH_USERS", "").split() if x.isdigit()),
    "REDIS_URI": "localhost:6379",
    "REDIS_PASS": "",
    "CHUNK_SIZE": int(os.environ.get("CHUNK_SIZE", 128)),
    "DEF_THUMB_NAIL_VID_S": os.environ.get("DEF_THUMB_NAIL_VID_S", ""),
    "MAX_MESSAGE_LENGTH": 4096,
    "PROCESS_MAX_TIMEOUT": 3600
}

for key, val in defaults.items():
    if not hasattr(Config, key):
        setattr(Config, key, val)

import pyrogram
from pyrogram import Client, filters, idle

# Patch missing filters.edited in Pyrogram v2
if not hasattr(filters, "edited"):
    filters.edited = filters.create(lambda _, __, ___: False)

async def main():
    os.makedirs(Config.DOWNLOAD_LOCATION, exist_ok=True)
    os.makedirs(Config.ADMIN_LOCATION, exist_ok=True)
    os.makedirs(Config.CREDENTIALS_LOCATION, exist_ok=True)

    app = Client(
        "Mega_Link_Downloader_Bot",
        bot_token=Config.TG_BOT_TOKEN,
        api_id=Config.APP_ID,
        api_hash=Config.API_HASH,
        plugins=dict(root="plugins")
    )
    
    await app.start()
    logging.info(">>> BOT STARTED SUCCESSFULLY! <<<")
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())run_until_complete(main())
