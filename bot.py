import os
import time
import random
import string
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
import aiohttp
import aiofiles

# --- جلب المتغيرات من بيئة التشغيل (Railway Environment Variables) ---
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SESSION_STRING = os.getenv("SESSION_STRING", "") # اختياري: إذا أردت تشغيله كـ Userbot
WEBSERVER_BASE_URL = os.getenv("WEBSERVER_BASE_URL", "yourdomain.com").rstrip('/')
FILES_EXPIRE_TIME = int(os.getenv("FILES_EXPIRE_TIME", "86400")) # 24 ساعة بالثواني

# 2 جيجابايت بالبايت (الحد الأقصى المسموح لتليجرام)
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024 

FILES_PATH = os.path.join(os.getcwd(), "files")
os.makedirs(FILES_PATH, exist_ok=True)

# إدارة جلسة البوت أو الحساب الشخصي
if SESSION_STRING:
    app = Client("uploadit_session", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
else:
    app = Client("uploadit_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

latest_speedtest = {}

# --- دوال مساعدة ---
def format_bytes(size: int) -> str:
    if size <= 0:
        return "0 B"
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while size >= 1024 and i < len(units) - 1:
        size /= 1024.0
        i += 1
    return f"{size:.2f} {units[i]}"

def generate_random_string(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

async def progress_callback(current, total, status_msg: Message, action_text: str, state_data: dict):
    """دالة لتحديث نسبة التقدم دون تجاوز حدود تليجرام في تعديل الرسائل"""
    now = time.time()
    if total > 0:
        percentage = round((current / total) * 100)
    else:
        percentage = 0

    last_time = state_data.get("last_time", 0)
    last_percentage = state_data.get("last_percentage", 0)

    # التحديث عند تغير النسبة بأكثر من 4% أو مرور ثانيتين على الأقل
    if (percentage - last_percentage >= 4) or (now - last_time >= 2):
        state_data["last_percentage"] = percentage
        state_data["last_time"] = now
        try:
            if "url" in state_data:
                part_str = f" [Part {state_data['part_num']}]" if "part_num" in state_data else ""
                text = (
                    f"📤 Your request is in the queue{part_str}. Please be patient…\n"
                    f"🗂 File: {state_data['filename']}\n"
                    f"🔗 URL: {state_data['url']}\n"
                    f"💿 File Size: {format_bytes(total)}\n\n"
                    f"⌛ Upload progress: {percentage}%"
                )
            else:
                text = f"{action_text}… {percentage}%"
            await status_msg.edit_text(text)
        except Exception:
            pass

async def split_file(filepath: str, max_size: int = MAX_FILE_SIZE):
    """دالة لتقسيم الملفات التي تتجاوز حجم 2 جيجابايت إلى أجزاء متعددة"""
    parts = []
    file_size = os.path.getsize(filepath)
    
    if file_size <= max_size:
        return [filepath]

    chunk_size = 1024 * 1024 * 10 # 10MB لكل لفة قراءة
    part_num = 1
    
    async with aiofiles.open(filepath, 'rb') as src_file:
        while True:
            part_filename = f"{filepath}.part{part_num:03d}"
            written_bytes = 0
            
            async with aiofiles.open(part_filename, 'wb') as dest_file:
                while written_bytes < max_size:
                    to_read = min(chunk_size, max_size - written_bytes)
                    chunk = await src_file.read(to_read)
                    if not chunk:
                        break
                    await dest_file.write(chunk)
                    written_bytes += len(chunk)

            if written_bytes == 0:
                if os.path.exists(part_filename):
                    os.remove(part_filename)
                break

            parts.append(part_filename)
            part_num += 1

    return parts

async def auto_delete_expired_files():
    """مهمة خلفية لحذف الملفات القديمة التي تجاوزت مدة صلاحيتها"""
    while True:
        try:
            now = time.time()
            for filename in os.listdir(FILES_PATH):
                file_path = os.path.join(FILES_PATH, filename)
                if os.path.isfile(file_path):
                    file_age = now - os.path.getctime(file_path)
                    if file_age > FILES_EXPIRE_TIME:
                        os.remove(file_path)
        except Exception as e:
            print(f"Error in auto delete: {e}")
        await asyncio.sleep(600) # فحص كل 10 دقائق

# --- أوامر البوت ---

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    text = (
        "Hi! please send me any file url or file uploaded in Telegram "
        "and I will upload to Telegram as file or generate download link of that file.\n\n"
        "Kindly Donate @ConQuerorRobot If You Like This\n"
        "Support Group @CuratorCrew"
    )
    await message.reply_text(text, quote=True)

@app.on_message(filters.command("speedtest"))
async def speedtest_command(client, message: Message):
    user_id = message.from_user.id if message.from_user else message.chat.id
    now = time.time()
    
    if user_id in latest_speedtest and (now - latest_speedtest[user_id] < 3600):
        await message.reply_text("You can test speed once per hour.", quote=True)
        return

    latest_speedtest[user_id] = now
    status_msg = await message.reply_text("Testing download and upload speed…", quote=True)

    try:
        process = await asyncio.create_subprocess_exec(
            "speedtest-cli", "--simple",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        output = stdout.decode().strip()
        if output:
            await status_msg.edit_text(output)
        else:
            await status_msg.edit_text("Error while testing speed.")
    except Exception as e:
        await status_msg.edit_text(f"Error executing speedtest: {e}")

# --- تحويل الوسائط المستقبلة من تليجرام إلى رابط تحميل مباشر ---

@app.on_message(filters.document | filters.photo | filters.video | filters.audio | filters.voice)
async def media_handler(client, message: Message):
    status_msg = await message.reply_text("Generating download link… 0%", quote=True)
    start_time = time.time()
    state_data = {"last_percentage": 0, "last_time": start_time}

    # تحديد الاسم والمصار
    original_filename = getattr(message.document or message.video or message.audio, "file_name", None)
    if not original_filename:
        ext = ".jpg" if message.photo else ".bin"
        original_filename = f"{int(time.time())}_{generate_random_string(5)}{ext}"

    safe_filename = f"{int(time.time())}_{generate_random_string(4)}_{original_filename}"
    file_path = os.path.join(FILES_PATH, safe_filename)

    try:
        await message.download(
            file_name=file_path,
            progress=progress_callback,
            progress_args=(status_msg, "Generating download link", state_data)
        )
        
        elapsed = round(time.time() - start_time)
        encoded_path = safe_filename.replace(' ', '%20')
        download_url = f"{WEBSERVER_BASE_URL}/{encoded_path}"

        result_text = (
            f"Download link Generated in {elapsed} seconds!\n\n"
            f"💾 {original_filename}\n\n"
            f"📥 {download_url}\n\n"
            f"This link will be expired in 24 hours."
        )
        await status_msg.edit_text(result_text)
    except Exception as e:
        await status_msg.edit_text(f"An error occurred: {e}")

# --- تنزيل الملفات من رابط خارجي ورفعها إلى تليجرام (مع دعم التقسيم) ---

@app.on_message(filters.text & ~filters.command(["start", "speedtest"]))
async def url_handler(client, message: Message):
    text = message.text.strip()
    parts = text.split('|', 1)
    url = parts[0].strip()
    
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.reply_text("URL format is incorrect. make sure your URL starts with either http:// or https://.", quote=True)
        return

    if len(parts) > 1 and parts[1].strip():
        filename = parts[1].strip()
    else:
        filename = url.split('/')[-1].split('?')[0]

    if not filename:
        await message.reply_text("Can you check your URL? I'm unable to detect filename from the URL.", quote=True)
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    await message.reply_text(f"Failed to fetch URL. HTTP Status: {response.status}", quote=True)
                    return

                content_length = response.headers.get('Content-Length')
                if not content_length:
                    await message.reply_text("Unable to obtain file size.", quote=True)
                    return

                filesize = int(content_length)

                status_msg = await message.reply_text("Downloading file from URL…", quote=True)
                local_filename = f"{int(time.time())}_{generate_random_string(4)}_{filename}"
                filepath = os.path.join(FILES_PATH, local_filename)

                # تنزيل الملف محلياً
                async with aiofiles.open(filepath, 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        await f.write(chunk)

                # فحص الحجم وتقسيم الملف إن تطلب الأمر
                await status_msg.edit_text("Checking file size & splitting if required…")
                split_parts = await split_file(filepath, MAX_FILE_SIZE)

                start_time = time.time()

                # رفع الأجزاء لتليجرام
                for idx, part_path in enumerate(split_parts, start=1):
                    part_filename = os.path.basename(part_path)
                    state_data = {
                        "last_percentage": 0,
                        "last_time": time.time(),
                        "filename": part_filename,
                        "url": url,
                        "part_num": f"{idx}/{len(split_parts)}"
                    }

                    await client.send_document(
                        chat_id=message.chat.id,
                        document=part_path,
                        file_name=part_filename,
                        reply_to_message_id=message.id,
                        progress=progress_callback,
                        progress_args=(status_msg, f"Uploading part {idx}/{len(split_parts)}", state_data)
                    )

                    # تنظيف الجزئية بعد رفعها
                    if os.path.exists(part_path) and part_path != filepath:
                        os.remove(part_path)

                elapsed_seconds = int(time.time() - start_time)
                hours, remainder = divmod(elapsed_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                time_str = "Uploaded… 100% in"
                if hours: time_str += f" {hours}h"
                if minutes: time_str += f" {minutes}m"
                if seconds: time_str += f" {seconds}s"

                await status_msg.edit_text(time_str)

                # تنظيف وحذف الملف الأصلي بعد الرفع الكامل
                if os.path.exists(filepath):
                    os.remove(filepath)

    except Exception as e:
        await message.reply_text(f"Error processing URL: {e}", quote=True)

# --- تشغيل البوت مع أداء المهمة الدورية ---

async def main():
    asyncio.create_task(auto_delete_expired_files())
    await app.start()
    print("Bot is running...")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
