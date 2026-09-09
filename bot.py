import os
import time
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
import yt_dlp

# إعداد السجلات بشكل يسهل تتبع الأخطاء في منصة Railway
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# قراءة المتغيرات بأمان لتجنب الكراش الفوري عند وجود مسافات أو قيم فارغة
def get_env_var(name, default=""):
    return os.environ.get(name, default).strip()

raw_api_id = get_env_var("API_ID", "0")
API_ID = int(raw_api_id) if raw_api_id.isdigit() else 0
API_HASH = get_env_var("API_HASH")
BOT_TOKEN = get_env_var("BOT_TOKEN")

if not all([API_ID, API_HASH, BOT_TOKEN]):
    logging.error("❌ تحذير: يرجى التأكد من ضبط API_ID و API_HASH و BOT_TOKEN في متغيرات البيئة.")

app = Client(
    "URL_Uploader_Bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# استيراد آمن لمكتبة curl_cffi لمنع توقف البوت إذا تعذر تحميل المكتبة البرمجية
CURL_CFFI_AVAILABLE = False
try:
    from curl_cffi import requests as cffi_requests
    CURL_CFFI_AVAILABLE = True
except Exception as e:
    logging.warning(f"لم يتم تحميل curl_cffi: {e}")

# هيدرز حديثة تحاكي متصفح Google Chrome حقيقي على نظام Windows
CUSTOM_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
    'Sec-Ch-Ua': '"Not-A.Brand";v="99", "Chromium";v="124", "Google Chrome";v="124"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
}

def humanbytes(size):
    if not size:
        return "0B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0

async def progress_bar(current, total, status_msg, start_time, title_action):
    now = time.time()
    diff = now - start_time
    if round(diff % 4) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff if diff > 0 else 0
        time_to_completion = round((total - current) / speed) if speed > 0 else 0
        
        progress = f"[{'■' * int(percentage / 10)}{'□' * (10 - int(percentage / 10))}] {percentage:.1f}%\n"
        status_text = (
            f"🚀 **{title_action}**\n\n"
            f"{progress}\n"
            f"⚡️ السرعة: **{humanbytes(speed)}/s**\n"
            f"📦 المحول: **{humanbytes(current)} / {humanbytes(total)}**\n"
            f"⏱ الوقت المتبقي: **{time_to_completion}s**"
        )
        try:
            await status_msg.edit_text(status_text)
        except Exception:
            pass

async def direct_curl_download(url, output_path):
    """سحب الفيديو تدفقياً عبر curl_cffi بتمويه بصمة TLS لتجاوز جدار Cloudflare"""
    if not CURL_CFFI_AVAILABLE:
        raise Exception("مكتبة تجاوز الحظر غير متوفرة على السيرفر.")

    loop = asyncio.get_running_loop()
    def _stream_download():
        res = cffi_requests.get(
            url,
            headers=CUSTOM_HEADERS,
            impersonate="chrome120",
            stream=True,
            timeout=60,
            verify=False
        )
        if res.status_code not in [200, 206]:
            raise Exception(f"فشل الاتصال بالرابط، كود الاستجابة: {res.status_code}")

        with open(output_path, 'wb') as f:
            for chunk in res.iter_content(chunk_size=2 * 1024 * 1024):
                if chunk:
                    f.write(chunk)
        return output_path

    return await loop.run_in_executor(None, _stream_download)

@app.on_message(filters.command("start"))
async def start_cmd(_, message: Message):
    await message.reply_text(
        "👋 **أهلاً بك في بوت التحميل المباشر المطور (v2)!**\n\n"
        "أرسل لي رابط الفيديو وسأقوم بسحبه وتجاوز حماية Cloudflare تلقائياً."
    )

@app.on_message(filters.text & filters.private & ~filters.command(["start"]))
async def process_url(client: Client, message: Message):
    url = message.text.strip()
    if not url.startswith(("http://", "https://")):
        return await message.reply_text("❌ يرجى إرسال رابط صحيح يبدأ بـ http أو https.")

    msg = await message.reply_text("⚡️ **جاري فك الحماية وسحب الفيديو...**")
    
    download_dir = f"downloads/{message.from_user.id}_{message.id}"
    os.makedirs(download_dir, exist_ok=True)
    out_template = os.path.join(download_dir, "%(title).50s.%(ext)s")

    # إعدادات متوافقة لا تتطلب وجود FFmpeg حتى لا ينهار السيرفر
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': out_template,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'cachedir': False,
        'user_agent': CUSTOM_HEADERS['User-Agent'],
        'http_headers': CUSTOM_HEADERS,
        'legacyserverconnect': True,
    }

    file_path = None
    video_title = "Direct_Video"

    try:
        loop = asyncio.get_running_loop()

        def download_yt():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                return filename, info.get('title', 'Video')

        # المحاولة الأولى: عبر yt-dlp
        try:
            file_path, video_title = await loop.run_in_executor(None, download_yt)
        except Exception as yt_err:
            logging.warning(f"yt-dlp failed ({yt_err}), switching to curl_cffi engine...")
            
            # المحاولة الثانية: التحويل التلقائي لمحرك curl_cffi لتجاوز 403 Cloudflare
            fallback_path = os.path.join(download_dir, "video.mp4")
            file_path = await direct_curl_download(url, fallback_path)

        if not file_path or not os.path.exists(file_path):
            files = os.listdir(download_dir)
            if files:
                file_path = os.path.join(download_dir, files[0])
            else:
                raise Exception("تعذر العثور على الملف بعد التنزيل.")

        await msg.edit_text("⬆️ **جاري الرفع إلى تليجرام...**")

        upload_start = time.time()
        await client.send_video(
            chat_id=message.chat.id,
            video=file_path,
            caption=f"🎬 **{video_title}**\n\n⚡️ تم السحب بنجاح (v2 Bypass)",
            progress=progress_bar,
            progress_args=(msg, upload_start, "جاري الرفع إلى تليجرام")
        )
        await msg.delete()

    except Exception as e:
        logging.error(f"Error handling URL {url}: {str(e)}")
        await msg.edit_text(f"❌ **حدث خطأ أثناء السحب:**\n`{str(e)[:150]}`")

    finally:
        if download_dir and os.path.exists(download_dir):
            for file in os.listdir(download_dir):
                try:
                    os.remove(os.path.join(download_dir, file))
                except Exception:
                    pass
            try:
                os.rmdir(download_dir)
            except Exception:
                pass

if __name__ == "__main__":
    app.run()
