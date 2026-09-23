import time
import os
import asyncio
import urllib.request
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
    """ربط IP سيرفر Railway بـ Proxy5 عبر الـ API"""
    proxy_key = os.getenv("PROXY_KEY", "").strip()
    if not proxy_key:
        return
    try:
        my_ip = urllib.request.urlopen('https://api.ipify.org', timeout=5).read().decode('utf8').strip()
        api_url = f"https://proxy5.net/api/g/setip?key={proxy_key}&ip={my_ip}"
        urllib.request.urlopen(api_url, timeout=5)
        print(f"✅ Bound Railway IP ({my_ip}) successfully.")
    except Exception as e:
        print(f"⚠️ Binding update failed: {e}")

def download_file_with_progress(url: str, output_path: str, progress_callback, proxy: str = None):
    # تجديد الربط قبل كل تنزيل
    refresh_proxy_binding()

    session = requests.Session()
    headers = {
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
        'Sec-Fetch-Site': 'same-site',
    }

    proxies = None
    if proxy:
        proxies = {
            "http": proxy,
            "https": proxy
        }

    response = session.get(
        url,
        headers=headers,
        impersonate="chrome124",
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

async def fetch_video(url: str, output_file: str, progress_callback, proxy: str = None):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, download_file_with_progress, url, output_file, progress_callback, proxy)
