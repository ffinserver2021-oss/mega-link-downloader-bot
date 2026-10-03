import os
import time
import math
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from mega import Mega
from helpers.display_progress import progress_for_pyrogram, humanbytes
from helpers.files_spliiting import split_files, split_video_files

# Safe Config import
try:
    from config import Config
except ImportError:
    class Config:
        DOWNLOAD_LOCATION = "./DOWNLOADS"
        AUTH_USERS = set()
        PROCESS_MAX_TIMEOUT = 3600

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
        m = Mega()
        # Initialize mega client anonymously
        try:
            m = m.login()
        except Exception:
            pass

        # Fetch URL info safely
        try:
            file_info = m.get_public_url_info(url)
            if isinstance(file_info, dict) and "name" in file_info:
                fname = file_info["name"]
        except Exception as e:
            logging.warning(f"Could not retrieve file_info: {e}")

        await status_msg.edit_text(f"📥 Downloading: `{fname}`\nPlease wait...")
        start_time = time.time()

        # Download the file
        download_path = m.download_url(url, dest_path=download_dir, dest_filename=fname)

        if not download_path or not os.path.exists(str(download_path)):
            # If download_url didn't return path directly, look inside dest_path
            possible_file = os.path.join(download_dir, fname)
            if os.path.exists(possible_file):
                download_path = possible_file
            else:
                await status_msg.edit_text("❌ Download failed: File not found on disk.")
                return

        file_size = os.path.getsize(download_path)
        await status_msg.edit_text(f"📤 Uploading: `{os.path.basename(download_path)}` ({humanbytes(file_size)})...")

        # Telegram 2GB Limit check
        if file_size > 2000 * 1024 * 1024:
            await status_msg.edit_text("✂️ File is larger than 2GB. Splitting file...")
            split_files_list = split_files(download_path)
            for part in split_files_list:
                await client.send_document(
                    chat_id=message.chat.id,
                    document=part,
                    caption=f"`{os.path.basename(part)}`",
                    reply_to_message_id=message.id
                )
                if os.path.exists(part):
                    os.remove(part)
            await status_msg.delete()
        else:
            # Upload normally
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
            "• Make sure it is a single file link (folder links require folder support)."
        )
