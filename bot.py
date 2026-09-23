import os
import time
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from downloader import fetch_video, format_bytes, format_time

# قراءة المتغيرات من بيئة التشغيل
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

logging.basicConfig(level=logging.INFO)

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise ValueError("❌ خطأ: يجب إدخال API_ID و API_HASH و BOT_TOKEN في متغيرات البيئة (Variables) في Railway!")

app = Client("shahid_bot_v3", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

def make_progress_bar(current, total, length=10):
    if total <= 0:
        return "░" * length
    percentage = current / total
    filled = int(length * percentage)
    return "█" * filled + "░" * (length - filled)

@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    await message.reply_text("مرحباً بك! أرسل لي رابط الفيديو وسأقوم بتحميله لك مع عرض لوحة التقدم المباشرة.")

@app.on_message(filters.text & filters.private)
async def handle_video_download(client: Client, message: Message):
    if message.text.startswith("/"):
        return

    url = message.text.strip()

    if "b2.shahidtv.net" not in url and "shahidtv.net" not in url:
        await message.reply_text("الرابط غير مدعوم. يرجى إرسال رابط صحيح من النطاق المطلوب.")
        return

    status_msg = await message.reply_text("⏳ جاري الاتصال بالسيرفر والتغلب على حماية Cloudflare...")
    output_filename = f"video_{message.id}.mp4"
    
    loop = asyncio.get_running_loop()
    last_update = [0]

    # تقدم التنزيل من السيرفر
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

    # تقدم الرفع إلى تلجرام
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
        await fetch_video(url, output_filename, download_progress)
        
        await status_msg.edit_text("⬆️ اكتمل التحميل، جاري بدء الرفع...")
        
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

async def main():
    await app.start()
    print("✅ تم تشغيل البوت بنجاح...")
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())