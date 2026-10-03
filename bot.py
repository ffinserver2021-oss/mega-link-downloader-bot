import asyncio
import os
import sys
import time
import glob
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import HTTPServer, BaseHTTPRequestHandler

# Set root path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Clean up any stale locked session files from crash
for s_file in glob.glob("*.session*"):
    try:
        os.remove(s_file)
    except Exception:
        pass

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Dummy Health Server for Render
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

# In-Memory Mock Redis
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

import types
cfg_mod = types.ModuleType("config")
cfg_mod.Config = Config
sys.modules["config"] = cfg_mod
sample_cfg = types.ModuleType("sample_config")
sample_cfg.Config = Config
sys.modules["sample_config"] = sample_cfg

# Mega patch to run without login
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

def humanbytes(size):
    if not size: return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size) < 1024.0: return f"{size:3.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"

last_edit_time = {}

async def pyrogram_upload_progress(current, total, client, message_id, chat_id, start_time, file_name):
    now = time.time()
    key = f"{chat_id}_{message_id}"
    if key in last_edit_time and (now - last_edit_time[key]) < 3.5 and current != total:
        return
    last_edit_time[key] = now
    diff = max(0.1, now - start_time)
    pct = round((current * 100) / total, 1)
    speed = current / diff
    filled = int(pct // 10)
    bar = "■" * filled + "□" * (10 - filled)
    text = (
        f"📤 **Uploading to Telegram...**\n"
        f"📄 `{file_name}`\n"
        f"[{bar}] **{pct}%**\n"
        f"⚡ **Speed:** {humanbytes(speed)}/s\n"
        f"📦 **Done:** {humanbytes(current)} / {humanbytes(total)}"
    )
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text)
    except Exception:
        pass

# In-Memory Client Session to eliminate sqlite session lock
app = Client(
    name="bot_session_clean",
    in_memory=True,
    bot_token=Config.TG_BOT_TOKEN,
    api_id=Config.APP_ID,
    api_hash=Config.API_HASH
)

@app.on_message(filters.command(["start", "help"]))
async def start_handler(client, message):
    await message.reply_text(
        "👋 **Bot is Active and Ready!**\n\n"
        "Send any `https://mega.nz/...` file link to download.\n\n"
        "*(Note: For smooth operation on free tier, keep file sizes under 400 MB)*"
    )

@app.on_message(filters.regex(r"https?://mega(\.co)?\.nz/.*"))
async def mega_dl_handler(client, message):
    url = message.text.strip()
    status_msg = await message.reply_text("⚡ Processing Mega link...", quote=True)

    fname = f"mega_file_{int(time.time())}"
    total_size = 0
    download_dir = Config.DOWNLOAD_LOCATION
    os.makedirs(download_dir, exist_ok=True)

    try:
        from mega import Mega
        m = Mega()
        try: m = m.login()
        except Exception: pass

        try:
            info = m.get_public_url_info(url)
            if isinstance(info, dict):
                fname = info.get("name", fname)
                total_size = info.get("size", 0)
        except Exception as e:
            logging.warning(f"Metadata error: {e}")

        # Strict safety check for Render 512MB RAM
        if total_size > 500 * 1024 * 1024:
            await status_msg.edit_text(
                f"⚠️ **File is too large ({humanbytes(total_size)})!**\n\n"
                "Render free tier server only has 512MB RAM. To prevent server crash, please download files under **500 MB**."
            )
            return

        await status_msg.edit_text(f"📥 **Downloading:** `{fname}`\nPlease wait...")
        start_time = time.time()
        target_path = os.path.join(download_dir, fname)

        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=2)
        download_future = loop.run_in_executor(
            executor,
            lambda: m.download_url(url, dest_path=download_dir, dest_filename=fname)
        )

        while not download_future.done():
            await asyncio.sleep(3)
            current_size = 0
            if os.path.exists(target_path):
                current_size = os.path.getsize(target_path)
            else:
                for f in os.listdir(download_dir):
                    fp = os.path.join(download_dir, f)
                    if os.path.isfile(fp):
                        current_size = max(current_size, os.path.getsize(fp))

            if total_size > 0 and current_size > 0:
                diff = max(0.1, time.time() - start_time)
                pct = min(100.0, round((current_size / total_size) * 100, 1))
                speed = current_size / diff
                filled = int(pct // 10)
                bar = "■" * filled + "□" * (10 - filled)
                text = (
                    f"📥 **Downloading from Mega...**\n"
                    f"📄 `{fname}`\n"
                    f"[{bar}] **{pct}%**\n"
                    f"⚡ **Speed:** {humanbytes(speed)}/s\n"
                    f"📦 **Done:** {humanbytes(current_size)} / {humanbytes(total_size)}"
                )
                try:
                    await status_msg.edit_text(text)
                except Exception:
                    pass

        download_path = await download_future

        if not download_path or not os.path.exists(str(download_path)):
            if os.path.exists(target_path):
                download_path = target_path
            else:
                await status_msg.edit_text("❌ Download failed.")
                return

        file_size = os.path.getsize(download_path)
        actual_name = os.path.basename(download_path)
        upload_start = time.time()

        await status_msg.edit_text(f"📤 Preparing upload for `{actual_name}` ({humanbytes(file_size)})...")

        await client.send_document(
            chat_id=message.chat.id,
            document=download_path,
            caption=f"📁 `{actual_name}`\n📦 Size: `{humanbytes(file_size)}`",
            reply_to_message_id=message.id,
            progress=pyrogram_upload_progress,
            progress_args=(client, status_msg.id, message.chat.id, upload_start, actual_name)
        )

        try:
            await status_msg.delete()
        except Exception:
            pass

        if os.path.exists(download_path):
            os.remove(download_path)

    except Exception as e:
        logging.error(f"Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ **Error:** `{e}`")

async def main():
    os.makedirs(Config.DOWNLOAD_LOCATION, exist_ok=True)
    await app.start()
    logging.info(">>> BOT STARTED SUCCESSFULLY AND CLEAN! <<<")
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
