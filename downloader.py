import time
import os
import asyncio
import yt_dlp
from urllib.parse import urlparse
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

def download_via_curl_cffi(url: str, output_path: str, progress_callback, proxies: dict = None) -> bool:
    """المحاولة الأولى: استخدام curl_cffi مع بصمة chrome124 وترويسات مخصصة"""
    print("[Method 1] Attempting download via curl_cffi...")
    session = requests.Session(impersonate="chrome124")
    
    # 1. إعداد الترويسات لمحاكاة متصفح Chrome حقيقي 100%
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
        'Referer': 'https://shahidtv.net/',
        'Origin': 'https://shahidtv.net',
        'Sec-Ch-Ua': '"Chromium";v="128", "Not=A?Brand";v="24", "Google Chrome";v="128"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'video',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site',
    }

    # تهيئة الجلسة مع الموقع الرئيسي لجلب الكوكيز لتجاوز حماية Cloudflare
    try:
        session.get("https://b2.shahidtv.net/", headers={'User-Agent': headers['User-Agent']}, proxies=proxies, timeout=10)
    except Exception as e:
        print(f"Handshake notice: {e}")

    # طلب ملف الميديا
    response = session.get(url, headers=headers, stream=True, allow_redirects=True, proxies=proxies, timeout=45)
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

    return os.path.exists(output_path) and os.path.getsize(output_path) > 0

def download_via_ytdlp(url: str, output_path: str, progress_callback, active_proxy: str = None) -> bool:
    """المحاولة الثانية: الاحتياطية باستخدام yt-dlp محاكية للمتصفح"""
    print("[Method 2] Fallback: Attempting download via yt-dlp...")
    
    start_time = time.time()
    
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
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [ytdlp_hook],
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
            'Referer': 'https://b2.shahidtv.net/',
            'Origin': 'https://b2.shahidtv.net',
            'Accept': '*/*',
        },
        'impersonate': 'chrome124',
    }

    if active_proxy:
        ydl_opts['proxy'] = active_proxy

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return os.path.exists(output_path) and os.path.getsize(output_path) > 0

def perform_download(url: str, output_path: str, progress_callback, proxy: str = None):
    env_proxy = os.getenv("PROXY_URL", "").strip()
    active_proxy = proxy if (proxy and proxy.strip()) else env_proxy

    proxies = None
    if active_proxy:
        proxies = {
            "http": active_proxy,
            "https": active_proxy
        }

    # المحاولة الأولى: عبر curl_cffi
    try:
        success = download_via_curl_cffi(url, output_path, progress_callback, proxies)
        if success:
            print("Download completed successfully with curl_cffi.")
            return
    except Exception as e:
        print(f"curl_cffi failed: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)

    # المحاولة الثانية (Fallback): عبر yt-dlp
    try:
        success = download_via_ytdlp(url, output_path, progress_callback, active_proxy)
        if success:
            print("Download completed successfully with yt-dlp.")
            return
    except Exception as e:
        print(f"yt-dlp failed: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
            
    raise Exception("فشلت جميع محاولات التنزيل. يرجى التأكد من صحة البروكسي ورابط الفيديو.")

def verify_download(output_path: str) -> bool:
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0

async def fetch_video(url: str, output_file: str, progress_callback, proxy: str = None):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, perform_download, url, output_file, progress_callback, proxy)
