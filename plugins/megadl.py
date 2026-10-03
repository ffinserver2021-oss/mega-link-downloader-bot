import os
import sys
import time
import math
import asyncio
import logging
from pyrogram import Client, filters

# Safe Config import
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
    if round(diff % 10.00) == 0 or current == total:
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
    if Config.AUTH_USERS and message.from_user.id not in Config.AUTH_USERS:
        await message.reply_text("You are not authorized to use this bot.")
        return

    url = message.text.strip()
    status_msg = await message.reply_text("⚡ Processing Mega link...", quote=True)

    fname = f"mega_file_{int(time.time())}"
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
            if isinstance(file_info, dict) and "name" in file_info:
                fname = file_info["name"]
        except Exception as e:
            logging.warning(f"Could not retrieve file_info: {e}")

        await status_msg.edit_text(f"📥 Downloading: `{fname}`\nPlease wait...")
        start_time = time.time()

        download_path = m.download_url(url, dest_path=download_dir, dest_filename=fname)

        if not download_path or not os.path.exists(str(download_path)):
            possible_file = os.path.join(download_dir, fname)
            if os.path.exists(possible_file):
                download_path = possible_file
            else:
                await status_msg.edit_text("❌ Download failed: File not found on disk.")
                return

        file_size = os.path.getsize(download_path)
        await status_msg.edit_text(f"📤 Uploading: `{os.path.basename(download_path)}` ({humanbytes(file_size)})...")

        await client.send_document(
            chat_id=message.chat.id,
            document=download_path,
            caption=f"`{os.path.basename(download_path)}`",
            reply_to_message_id=message.id,
            progress=progress_for_pyrogram,
            progress_args=("Uploading...", status_msg, start_time)
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
