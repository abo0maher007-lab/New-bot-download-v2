import time
import os
import asyncio
import urllib.request
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

def refresh_proxy_binding():
    """ربط IP سيرفر Railway تلقائياً بـ Proxy5 لتفادي Connection Timeout"""
    proxy_key = os.getenv("PROXY_KEY", "").strip()
    if not proxy_key:
        return
    try:
        # جلب الـ IP الحالي للسيرفر
        my_ip = urllib.request.urlopen('https://api.ipify.org', timeout=5).read().decode('utf8').strip()
        # إرسال طلب التعيين لـ Proxy5 API
        api_url = f"https://proxy5.net/api/g/setip?key={proxy_key}&ip={my_ip}"
        urllib.request.urlopen(api_url, timeout=5)
        print(f"✅ Auto-bound Railway IP ({my_ip}) to Proxy5 successfully.")
    except Exception as e:
        print(f"⚠️ Proxy binding update failed: {e}")

def download_with_ytdlp(url: str, output_path: str, progress_callback, proxy: str = None):
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
        'socket_timeout': 15,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'http_headers': {
            'Referer': 'https://shahidtv.net/',
            'Origin': 'https://shahidtv.net',
            'Accept': '*/*',
            'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
        }
    }

    if proxy:
        ydl_opts['proxy'] = proxy

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def download_file_with_progress(url: str, output_path: str, progress_callback, proxy: str = None):
    # تفعيل وتجديد ربط الـ IP قبل كل عملية تحميل
    refresh_proxy_binding()

    try:
        download_with_ytdlp(url, output_path, progress_callback, proxy)
    except Exception as e:
        print(f"yt-dlp error: {e}, falling back to direct stream...")
        # إذا فشل البروكسي يتجاوزه ويحمل مباشرة من سيرفر Railway
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
            'Referer': 'https://shahidtv.net/',
            'Origin': 'https://shahidtv.net',
        }
        response = session.get(url, headers=headers, impersonate="chrome124", stream=True, timeout=20)
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
                        elapsed = now - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        eta = (total_length - downloaded) / speed if speed > 0 and total_length > 0 else 0
                        if progress_callback:
                            progress_callback(downloaded, total_length, speed, eta)

async def fetch_video(url: str, output_file: str, progress_callback, proxy: str = None):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, download_file_with_progress, url, output_file, progress_callback, proxy)
