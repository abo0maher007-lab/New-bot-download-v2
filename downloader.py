import time
import asyncio
import yt_dlp
from curl_cffi import requests

def format_bytes(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

def format_time(seconds):
    if seconds < 0 or seconds > 86400:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def download_with_ytdlp(url: str, output_path: str, progress_callback):
    def ytdlp_hook(d):
        if d['status'] == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            speed = d.get('speed', 0) or 0
            eta = d.get('eta', 0) or 0
            if progress_callback:
                progress_callback(downloaded, total, speed, eta)

    ydl_opts = {
        'outtmpl': output_path,
        'concurrent_fragment_downloads': 1,
        'progress_hooks': [ytdlp_hook],
        'nocheckcertificate': True,
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'http_headers': {
            'Referer': 'https://shahidtv.net/',
            'Origin': 'https://shahidtv.net',
            'Accept': '*/*',
            'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
        }
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def download_with_curlcffi(url: str, output_path: str, progress_callback):
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Accept': 'video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5',
        'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
        'Referer': 'https://shahidtv.net/',
        'Origin': 'https://shahidtv.net',
        'Range': 'bytes=0-',
    }

    response = session.get(
        url,
        headers=headers,
        impersonate="chrome124",
        stream=True,
        allow_redirects=True,
        timeout=120
    )
    
    response.raise_for_status()
    total_length = int(response.headers.get('content-length', 0))

    downloaded = 0
    start_time = time.time()
    last_update_time = start_time

    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=2 * 1024 * 1024):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                now = time.time()
                if now - last_update_time >= 1.5 or (total_length > 0 and downloaded == total_length):
                    last_update_time = now
                    elapsed_time = now - start_time
                    speed = downloaded / elapsed_time if elapsed_time > 0 else 0
                    eta = (total_length - downloaded) / speed if speed > 0 and total_length > 0 else 0
                    if progress_callback:
                        progress_callback(downloaded, total_length, speed, eta)

def download_file_with_progress(url: str, output_path: str, progress_callback):
    # محاولة التحميل بـ yt-dlp أولاً لتجاوز الحظر
    try:
        download_with_ytdlp(url, output_path, progress_callback)
    except Exception:
        # البديل الثاني عبر curl_cffi المطور
        download_with_curlcffi(url, output_path, progress_callback)

async def fetch_video(url: str, output_file: str, progress_callback):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, download_file_with_progress, url, output_file, progress_callback)
