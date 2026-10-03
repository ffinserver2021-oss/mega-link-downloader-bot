import asyncio
import os
import sys
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Add root project path to sys.path so helpers can be imported from anywhere
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Render Port Check
class SimpleHealthCheck(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHealthCheck)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

# Dummy Redis
class MockRedis:
    def __init__(self, *args, **kwargs):
        self.store = {}
    def ping(self): return True
    def set(self, name, value, *args, **kwargs):
        self.store[name] = value; return True
    def get(self, name): return self.store.get(name)
    def delete(self, *names):
        for n in names: self.store.pop(n, None)
        return True
    def smembers(self, name): return self.store.get(name, set())
    def sadd(self, name, *values):
        s = self.store.setdefault(name, set())
        for v in values: s.add(str(v).encode() if isinstance(v, str) else v)
        return True
    def srem(self, name, *values):
        s = self.store.setdefault(name, set())
        for v in values: s.discard(str(v).encode() if isinstance(v, str) else v)
        return True
    def sismember(self, name, value):
        s = self.store.get(name, set())
        return (str(value).encode() if isinstance(value, str) else value) in s

import redis
redis.Redis = MockRedis
redis.StrictRedis = MockRedis

# Safe Config
class SafeConfigMeta(type):
    def __getattr__(cls, name):
        val = os.environ.get(name, "")
        if name in ["APP_ID", "CHUNK_SIZE", "PROCESS_MAX_TIMEOUT"]:
            try: return int(val) if val else 0
            except ValueError: return 0
        if name == "AUTH_USERS":
            return set(int(x) for x in val.split() if x.isdigit())
        if name in ["DOWNLOAD_LOCATION", "ADMIN_LOCATION", "CREDENTIALS_LOCATION"]:
            return val or f"./{name.lower()}"
        return val

class Config(metaclass=SafeConfigMeta):
    TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", os.environ.get("BOT_TOKEN", ""))
    APP_ID = int(os.environ.get("APP_ID", os.environ.get("API_ID", 0)))
    API_HASH = os.environ.get("API_HASH", "")
    DOWNLOAD_LOCATION = os.environ.get("DOWNLOAD_LOCATION", "./DOWNLOADS")
    ADMIN_LOCATION = os.environ.get("ADMIN_LOCATION", "./plugins")
    CREDENTIALS_LOCATION = os.environ.get("CREDENTIALS_LOCATION", "./credentials")
    REDIS_URI = "localhost:6379"
    REDIS_PASS = ""

import types
cfg_mod = types.ModuleType("config")
cfg_mod.Config = Config
sys.modules["config"] = cfg_mod
sample_cfg = types.ModuleType("sample_config")
sample_cfg.Config = Config
sys.modules["sample_config"] = sample_cfg

# Mega Anonymous Patch
try:
    import mega
    orig_login = mega.Mega.login
    def safe_login(self, email=None, password=None):
        if not email or not password:
            return self
        try: return orig_login(self, email, password)
        except Exception: return self
    mega.Mega.login = safe_login
except ImportError:
    pass

import pyrogram
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pyrogram.enums import ParseMode
import pyrogram.parser.parser

if not hasattr(filters, "edited"):
    filters.edited = filters.create(lambda _, __, ___: False)

Message.message_id = property(lambda self: self.id)

orig_parse = pyrogram.parser.parser.Parser.parse
def patched_parse(self, text, parse_mode=object):
    if isinstance(parse_mode, str):
        m = parse_mode.lower()
        if m in ("html", "default"): parse_mode = ParseMode.HTML
        elif m in ("md", "markdown"): parse_mode = ParseMode.MARKDOWN
        elif m == "disabled": parse_mode = ParseMode.DISABLED
    return orig_parse(self, text, parse_mode)
pyrogram.parser.parser.Parser.parse = patched_parse

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
    asyncio.get_event_loop().run_until_complete(main())
