import os
import time
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from downloader import fetch_video, format_bytes, format_time

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

app = Client("shahid_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

logging.basicConfig(level=logging.INFO)

def make_progress_bar(current, total, length=10):
    if total <= 0:
        return "░" * length
    percentage = current / total
    filled = int(length * percentage)
    return "█" * filled + "░" * (length - filled)

@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    await message.reply_text("مرحباً بك! أرسل لي رابط الفيديو من b2.shahidtv.net وسأقوم بتحميله لك مع عرض التقدم المباشر.")

@app.on_message(filters.text & ~filters.command)
async def handle_video_download(client: Client, message: Message):
    url = message.text.strip()

    if "b2.shahidtv.net" not in url:
        await message.reply_text("الرابط غير مدعوم. يرجى إرسال رابط صحيح من النطاق المطلوب.")
        return

    status_msg = await message.reply_text("⏳ جاري الاتصال بالسيرفر والتغلب على حماية Cloudflare...")
    output_filename = f"video_{message.id}.mp4"
    
    loop = asyncio.get_running_loop()
    last_update = [0]

    # كولباك لمتابعة تقدم التحميل من الخادم
    def download_progress(downloaded, total, speed, eta):
        now = time.time()
        if now - last_update[0] < 1.5 and downloaded != total:
            return
        last_update[0] = now

        percent = (downloaded / total * 100) if total > 0 else 0
        bar = make_progress_bar(downloaded, total)
        
        text = (
            f"⬇️ **جاري تحميل الفيديو من السيرفر...**\n\n"
            f"[{bar}] `{percent:.1f}%`\n\n"
            f"🚀 **السرعة:** `{format_bytes(speed)}/s`\n"
            f"📦 **المحمل:** `{format_bytes(downloaded)}` من `{format_bytes(total)}`\n"
            f"⏱ **الوقت المتبقي:** `{format_time(eta)}`"
        )
        
        asyncio.run_coroutine_threadsafe(status_msg.edit_text(text, parse_mode="Markdown"), loop)

    # كولباك لمتابعة تقدم الرفع إلى تلجرام
    start_upload_time = time.time()
    async def upload_progress(current, total):
        now = time.time()
        if now - last_update[0] < 1.5 and current != total:
            return
        last_update[0] = now

        percent = (current / total * 100) if total > 0 else 0
        bar = make_progress_bar(current, total)
        elapsed = now - start_upload_time
        speed = current / elapsed if elapsed > 0 else 0
        eta = (total - current) / speed if speed > 0 else 0

        text = (
            f"⬆️ **جاري رفع الفيديو إلى تلجرام...**\n\n"
            f"[{bar}] `{percent:.1f}%`\n\n"
            f"🚀 **السرعة:** `{format_bytes(speed)}/s`\n"
            f"📦 **المرفوع:** `{format_bytes(current)}` من `{format_bytes(total)}`\n"
            f"⏱ **الوقت المتبقي:** `{format_time(eta)}`"
        )
        
        try:
            await status_msg.edit_text(text, parse_mode="Markdown")
        except Exception:
            pass

    try:
        # التحميل
        await fetch_video(url, output_filename, download_progress)
        
        await status_msg.edit_text("⬆️ اكتمل التحميل، جاري بدء الرفع...")
        
        # الرفع
        await client.send_video(
            chat_id=message.chat.id,
            video=output_filename,
            caption="تم التحميل والرفع بنجاح!",
            supports_streaming=True,
            progress=upload_progress
        )
        
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Error: {e}")
        await status_msg.edit_text(f"❌ حدث خطأ أثناء العملية:\n`{str(e)}`", parse_mode="Markdown")
        
    finally:
        if os.path.exists(output_filename):
            os.remove(output_filename)

if __name__ == '__main__':
    print("البوت يعمل الآن بنجاح مع لوحة التقدم...")
    app.run()
