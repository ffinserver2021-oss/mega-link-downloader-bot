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

# Reliable Telegram Upload Progress Callback
last_edit_time = {}

async def pyrogram_upload_progress(current, total, client, message_id, chat_id, start_time, file_name):
    now = time.time()
    task_key = f"{chat_id}_{message_id}"
    
    # Update every 3.5 seconds or when 100% complete
    if task_key in last_edit_time and (now - last_edit_time[task_key]) < 3.5 and current != total:
        return

    last_edit_time[task_key] = now
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

        await status_msg.edit_text(f"📥 **Downloading:** `{fname}`\nConnecting to Mega...")
        start_time = time.time()
        target_path = os.path.join(download_dir, fname)

        # Background Mega Download
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=2)
        download_future = loop.run_in_executor(
            executor,
            lambda: m.download_url(url, dest_path=download_dir, dest_filename=fname)
        )

        # Progress monitor loop for downloading
        while not download_future.done():
            await asyncio.sleep(3)
            current_size = 0
            
            # Check target path or any temporary file created in the download directory
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
                await status_msg.edit_text("❌ Download failed: File not found.")
                return

        file_size = os.path.getsize(download_path)
        actual_name = os.path.basename(download_path)
        upload_start = time.time()

        await status_msg.edit_text(f"📤 Preparing upload for `{actual_name}` ({humanbytes(file_size)})...")

        # Upload with reliable progress updater
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
        logging.error(f"Error in mega_dl_handler: {e}", exc_info=True)
        await status_msg.edit_text(
            f"**Error:** `{e}`\n\n"
            "Sorry, some error occurred!\n"
            "• Make sure the link is valid and public."
                )
