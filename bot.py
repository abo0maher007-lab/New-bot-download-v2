import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from downloader import fetch_video

BOT_TOKEN = os.getenv("BOT_TOKEN", "ضع_توكن_البوت_هنا")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً بك! أرسل لي رابط الفيديو من b2.shahidtv.net وسأقوم بتحميله لك.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if "b2.shahidtv.net" not in url:
        await update.message.reply_text("الرابط غير مدعوم. يرجى إرسال رابط صحيح من النطاق المطلوب.")
        return

    status_msg = await update.message.reply_text("⏳ جاري التغلب على حماية Cloudflare وتنزيل الفيديو...")
    output_filename = f"video_{update.message.message_id}.mp4"

    try:
        await fetch_video(url, output_filename)
        
        await status_msg.edit_text("⬆️ جاري رفع الفيديو إلى تلجرام...")
        
        with open(output_filename, 'rb') as video_file:
            await update.message.reply_video(video=video_file, caption="تم التحميل بنجاح!")
            
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ حدث خطأ أثناء التحميل: {str(e)}")
    
    finally:
        if os.path.exists(output_filename):
            os.remove(output_filename)

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("البوت يعمل الآن...")
    app.run_polling()
