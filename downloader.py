import time
import os
import asyncio
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

def perform_download(url: str, output_path: str, progress_callback, proxy: str = None):
    # إنشاء جلسة impersonate لمحاكاة متصفح Chrome 124 وتجاوز فحص Cloudflare
    session = requests.Session(impersonate="chrome124")
    
    proxies = None
    env_proxy = os.getenv("PROXY_URL", "").strip()
    active_proxy = proxy if (proxy and proxy.strip()) else env_proxy

    if active_proxy:
        proxies = {
            "http": active_proxy,
            "https": active_proxy
        }

    # 1. زيارة الصفحة الرئيسية للموقع الأساسي لبناء كوكيز الحماية والجلسة
    main_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
    }
    try:
        session.get("https://shahidtv.net/", headers=main_headers, proxies=proxies, timeout=10)
    except Exception as e:
        print(f"Main site handshake skipped: {e}")

    # 2. إرسال طلب التنزيل لرابط الفيديو المباشر مع الترويسات المطلوبة
    download_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
        'Referer': 'https://shahidtv.net/',
        'Origin': 'https://shahidtv.net',
        'Sec-Ch-Ua': '"Chromium";v="128", "Not=A?Brand";v="24", "Google Chrome";v="128"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'video',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site',
        'Range': 'bytes=0-'
    }

    response = session.get(
        url,
        headers=download_headers,
        stream=True,
        allow_redirects=True,
        proxies=proxies,
        timeout=30
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
                    elapsed = now - start_time
                    speed = downloaded / elapsed if elapsed > 0 else 0
                    eta = (total_length - downloaded) / speed if speed > 0 and total_length > 0 else 0
                    if progress_callback:
                        progress_callback(downloaded, total_length, speed, eta)

def verify_download(output_path: str) -> bool:
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0

async def fetch_video(url: str, output_file: str, progress_callback, proxy: str = None):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, perform_download, url, output_file, progress_callback, proxy)
