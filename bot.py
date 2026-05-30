import glob
import logging
import os
import re

import imageio_ffmpeg
import yt_dlp
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")
COOKIES = os.getenv("COOKIES_TXT")

if not TOKEN:
    raise RuntimeError(
        "Missing TOKEN environment variable. Add your Telegram bot token in Railway Variables."
    )

if COOKIES:
    with open("cookies.txt", "w", encoding="utf-8") as f:
        f.write(COOKIES.replace("\\n", "\n"))


def extract_url(text):
    match = re.search(r"https?://\S+", text or "")
    return match.group(0) if match else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send YouTube / TikTok / Instagram link")


async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    url = extract_url(text)

    if not url:
        await update.message.reply_text("Send valid link.")
        return

    msg = await update.message.reply_text("Downloading...")
    os.makedirs("downloads", exist_ok=True)

    ydl_opts = {
        "format": "bestaudio/best",
        "extract_flat": False,
        "outtmpl": "downloads/%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "cookiefile": "cookies.txt" if os.path.exists("cookies.txt") else None,
        "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
        "extractor_args": {
            "youtube": {
                "player_client": ["android"],
            },
        },
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get("id")

        mp3_files = glob.glob(f"downloads/{video_id}.mp3")

        if not mp3_files:
            await update.message.reply_text("Failed.")
            return

        mp3_path = mp3_files[0]

        with open(mp3_path, "rb") as audio:
            await update.message.reply_audio(
                audio=audio,
                title=info.get("title", "music"),
            )

        await msg.delete()

    except Exception as e:
        logger.exception("Download failed")
        await msg.delete()
        await update.message.reply_text(f"Error:\n{e}")

    finally:
        for leftover in glob.glob("downloads/*"):
            try:
                os.remove(leftover)
            except OSError:
                logger.warning("Could not remove leftover file: %s", leftover)


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download))

print("Bot Running...")
app.run_polling()
