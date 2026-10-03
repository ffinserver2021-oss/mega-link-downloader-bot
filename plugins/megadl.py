import os
import sys
import time
import math
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pyrogram import Client, filters

try:
    from config import Config
except ImportError:
    class Config:
        DOWNLOAD_LOCATION = "./DOWNLOADS"
        AUTH_USERS = set()
        PROCESS_MAX_TIMEOUT = 3600

def humanbytes(size):
    if not size:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size) < 1024.0:
            return f"{size:3.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"

async def progress_for_pyrogram(current, total, ud_type, message, start):
    now = time.time()
    diff = now - start
    if round(diff % 5.00) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff if diff > 0 else 0
        elapsed_time = round(diff) * 1000
        time_to_completion = round((total - current) / speed) * 1000 if speed > 0 else 0
        progress_str = f"[{'■' * math.floor(percentage / 10)}{'□' * (10 - math.floor(percentage / 10))}]"
        tmp = f"{progress_str} {round(percentage, 2)}%\n" \
              f"**Total:** {humanbytes(total)}\n" \
              f"**Speed:** {humanbytes(speed)}/s\n" \
              f"**Done:** {humanbytes(current)}"
        try:
            await message.edit_text(f"{ud_type}\n{tmp}")
        except Exception:
            pass

@Client.on_message(filters.regex(r"https?://mega(\.co)?\.nz/.*") & filters.private)
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
        try:
            m = m.login()
        except Exception:
            pass

        try:
            file_info = m.get_public_url_info(url)
            if isinstance(file_info, dict):
                fname = file_info.get("name", fname)
                total_size = file_info.get("size", 0)
        except Exception as e:
            logging.warning(f"Could not retrieve file_info: {e}")

        await status_msg.edit_text(f"📥 Downloading: `{fname}`\nInitializing...")
        start_time = time.time()
        target_path = os.path.join(download_dir, fname)

        # Thread pool-এ ব্যাকগ্রাউন্ডে ডাউনলোড রান করা
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=2)
        download_future = loop.run_in_executor(
            executor,
            lambda: m.download_url(url, dest_path=download_dir, dest_filename=fname)
        )

        # লাইভ প্রগ্রেস মনিটরিং লুপ
        while not download_future.done():
            await asyncio.sleep(4)
            current_size = 0
            if os.path.exists(target_path):
                current_size = os.path.getsize(target_path)
            
            if total_size > 0 and current_size > 0:
                diff = time.time() - start_time
                pct = min(100.0, (current_size / total_size) * 100)
                speed = current_size / diff if diff > 0 else 0
                prog_bar = f"[{'■' * math.floor(pct / 10)}{'□' * (10 - math.floor(pct / 10))}]"
                text = (
                    f"📥 **Downloading:** `{fname}`\n"
                    f"{prog_bar} {round(pct, 2)}%\n"
                    f"**Total:** {humanbytes(total_size)}\n"
                    f"**Speed:** {humanbytes(speed)}/s\n"
                    f"**Done:** {humanbytes(current_size)}"
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
                await status_msg.edit_text("❌ Download failed: File not found on disk.")
                return

        file_size = os.path.getsize(download_path)
        upload_start = time.time()
        await status_msg.edit_text(f"📤 Uploading: `{os.path.basename(download_path)}` ({humanbytes(file_size)})...")

        await client.send_document(
            chat_id=message.chat.id,
            document=download_path,
            caption=f"`{os.path.basename(download_path)}`",
            reply_to_message_id=message.id,
            progress=progress_for_pyrogram,
            progress_args=("📤 **Uploading to Telegram...**", status_msg, upload_start)
        )
        await status_msg.delete()

        if os.path.exists(download_path):
            os.remove(download_path)

    except Exception as e:
        logging.error(f"Error in mega_dl_handler: {e}", exc_info=True)
        await status_msg.edit_text(
            f"**Error:** `{e}`\n\n"
            "Sorry, some error occurred!\n"
            "• Make sure the link is valid and public.\n"
            "• Make sure it is a single file link."
    )
