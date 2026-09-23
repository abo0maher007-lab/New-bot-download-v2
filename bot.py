import os
import time
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from downloader import fetch_video, format_bytes, format_time

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PROXY_URL = os.getenv("PROXY_URL", "").strip() or None

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

if not BOT_TOKEN:
    raise ValueError("❌ خطأ: لم يتم العثور على BOT_TOKEN في متغيرات البيئة!")

def make_progress_bar(current, total, length=10):
    if total <= 0:
        return "░" * length
    percentage = current / total
    filled = int(length * percentage)
    return "█" * filled + "░" * (length - filled)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً بك! أرسل لي رابط الفيديو وسأقوم بتحميله لك مع عرض لوحة التقدم المباشرة.")

async def handle_video_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if "b2.shahidtv.net" not in url and "shahidtv.net" not in url:
        await update.message.reply_text("الرابط غير مدعوم. يرجى إرسال رابط صحيح من النطاق المطلوب.")
        return

    status_msg = await update.message.reply_text("⏳ جاري الاتصال بالسيرفر والتغلب على حماية Cloudflare...")
    output_filename = f"video_{update.message.message_id}.mp4"
    
    loop = asyncio.get_running_loop()
    last_update = [0]

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
            f"📦 **المحمل:** `{format_bytes(downloaded)}` من `{format_bytes(total if total > 0 else downloaded)}`\n"
            f"⏱ **الوقت المتبقي:** `{format_time(eta)}`"
        )
        
        asyncio.run_coroutine_threadsafe(
            status_msg.edit_text(text, parse_mode="Markdown"), loop
        )

    try:
        await fetch_video(url, output_filename, download_progress, proxy=PROXY_URL)
        
        await status_msg.edit_text("⬆️ اكتمل التحميل من السيرفر، جاري رفع الفيديو إلى تلجرام...")
        
        with open(output_filename, 'rb') as video_file:
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=video_file,
                caption="تم التحميل والرفع بنجاح!",
                supports_streaming=True,
                read_timeout=600,
                write_timeout=600,
                connect_timeout=600
            )
            
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Error: {e}")
        await status_msg.edit_text(f"❌ حدث خطأ أثناء العملية:\n`{str(e)}`", parse_mode="Markdown")
        
    finally:
        if os.path.exists(output_filename):
            os.remove(output_filename)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_video_download))

    print("✅ تم تشغيل البوت بنجاح...")
    app.run_polling()

if __name__ == '__main__':
    main()
