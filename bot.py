import os
import time
import random
import string
import asyncio
import logging
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from aiohttp import web
import aiofiles
from curl_cffi.requests import AsyncSession

logging.basicConfig(level=logging.INFO)

# --- Variables ---
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
WEBSERVER_BASE_URL = os.getenv("WEBSERVER_BASE_URL", "yourdomain.com").rstrip('/')
FILES_EXPIRE_TIME = int(os.getenv("FILES_EXPIRE_TIME", "86400"))
PORT = int(os.getenv("PORT", "8080"))

MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024

FILES_PATH = os.path.join(os.getcwd(), "files")
os.makedirs(FILES_PATH, exist_ok=True)

# Client Initialization
if SESSION_STRING:
    app = Client("uploadit_session", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
else:
    app = Client("uploadit_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

latest_speedtest = {}

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

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
    now = time.time()
    percentage = round((current / total) * 100) if total > 0 else 0

    last_time = state_data.get("last_time", 0)
    last_percentage = state_data.get("last_percentage", 0)

    if (percentage - last_percentage >= 5) or (now - last_time >= 3):
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
    file_size = os.path.getsize(filepath)
    if file_size <= max_size:
        return [filepath]

    parts = []
    chunk_size = 1024 * 1024 * 10
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

async def download_with_ytdlp(url: str, output_template: str):
    cmd = [
        "yt-dlp",
        "--no-check-certificate",
        "--user-agent", DEFAULT_HEADERS["User-Agent"],
        "--referer", url,
        "--add-header", f"Accept:{DEFAULT_HEADERS['Accept']}",
        "--concurrent-fragments", "5",
        "-o", output_template,
        url
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()
    return process.returncode == 0

async def download_with_curl_cffi(url: str, filepath: str):
    try:
        headers = DEFAULT_HEADERS.copy()
        headers["Referer"] = url
        async with AsyncSession(impersonate="chrome120") as s:
            r = await s.get(url, headers=headers, stream=True)
            if r.status_code == 200:
                async with aiofiles.open(filepath, 'wb') as f:
                    async for chunk in r.aiter_content():
                        await f.write(chunk)
                return True
    except Exception as e:
        logging.error(f"curl_cffi Error: {e}")
    return False

async def auto_delete_expired_files():
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
            logging.error(f"Error in auto delete: {e}")
        await asyncio.sleep(600)

# --- Handlers ---
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message: Message):
    text = (
        "Hi! please send me any file url or file uploaded in Telegram "
        "and I will upload to Telegram as file or generate download link of that file.\n\n"
        "Kindly Donate @ConQuerorRobot If You Like This\n"
        "Support Group @CuratorCrew"
    )
    await message.reply_text(text, quote=True)

@app.on_message(filters.command("speedtest") & filters.private)
async def speedtest_command(client, message: Message):
    user_id = message.from_user.id
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
        await status_msg.edit_text(output if output else "Error while testing speed.")
    except Exception as e:
        await status_msg.edit_text(f"Error executing speedtest: {e}")

@app.on_message((filters.document | filters.photo | filters.video | filters.audio | filters.voice) & filters.private)
async def media_handler(client, message: Message):
    status_msg = await message.reply_text("Generating download link… 0%", quote=True)
    start_time = time.time()
    state_data = {"last_percentage": 0, "last_time": start_time}

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

@app.on_message(filters.text & filters.private & ~filters.command(["start", "speedtest"]))
async def url_handler(client, message: Message):
    text = message.text.strip()
    parts = text.split('|', 1)
    url = parts[0].strip()
    
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.reply_text("URL format is incorrect. make sure your URL starts with either http:// or https://.", quote=True)
        return

    custom_filename = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
    status_msg = await message.reply_text("Downloading file from URL…", quote=True)
    prefix = f"{int(time.time())}_{generate_random_string(4)}"
    
    filepath = None
    download_success = False

    filename = custom_filename or url.split('/')[-1].split('?')[0] or "video.mp4"
    local_filename = f"{prefix}_{filename}"
    target_filepath = os.path.join(FILES_PATH, local_filename)

    # 1. Bypass with curl_cffi
    if await download_with_curl_cffi(url, target_filepath):
        filepath = target_filepath
        download_success = True

    # 2. Bypass with yt-dlp
    if not download_success:
        output_template = os.path.join(FILES_PATH, f"{prefix}_%(title)s.%(ext)s")
        if await download_with_ytdlp(url, output_template):
            for f in os.listdir(FILES_PATH):
                if f.startswith(prefix):
                    filepath = os.path.join(FILES_PATH, f)
                    download_success = True
                    break

    if not download_success or not filepath or not os.path.exists(filepath):
        await status_msg.edit_text("❌ Error 403 / Forbidden: Unable to download file. Link might require authentication or restricted domain.")
        return

    try:
        await status_msg.edit_text("Checking file size & splitting if required…")
        split_parts = await split_file(filepath, MAX_FILE_SIZE)

        start_time = time.time()

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

        if os.path.exists(filepath):
            os.remove(filepath)

    except Exception as e:
        await message.reply_text(f"Error processing URL: {e}", quote=True)

# --- Web Server Routes ---
async def handle_ping(request):
    return web.Response(text="Bot is Alive!")

async def web_app():
    server = web.Application()
    server.router.add_get("/", handle_ping)
    server.router.add_get("/health", handle_ping)
    server.router.add_static("/", FILES_PATH)
    return server

# --- Main Entry ---
async def main():
    # Start Webserver Runner
    app_runner = web.AppRunner(await web_app())
    await app_runner.setup()
    site = web.TCPSite(app_runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Web server running on port {PORT}")

    # Start Background Task
    cleaner_task = asyncio.create_task(auto_delete_expired_files())

    # Start Pyrogram
    await app.start()
    logging.info("Bot started successfully and is ready!")

    try:
        await idle()
    finally:
        # Graceful Shutdown compatible with Python 3.13
        cleaner_task.cancel()
        await app.stop()
        await app_runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
