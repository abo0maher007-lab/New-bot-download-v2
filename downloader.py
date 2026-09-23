import time
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

def download_file_with_progress(url: str, output_path: str, progress_callback):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
        'Referer': 'https://shahidtv.net/',
        'Origin': 'https://shahidtv.net',
        'Sec-Ch-Ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'video',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
    }

    response = requests.get(
        url,
        headers=headers,
        impersonate="chrome124",
        stream=True,
        timeout=300
    )
    
    response.raise_for_status()
    total_length = int(response.headers.get('content-length', 0))

    downloaded = 0
    start_time = time.time()
    last_update_time = start_time

    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                
                now = time.time()
                # تحديث التقرير كل ثانية ونصف لتجنب حظر Flood limit في تلجرام
                if now - last_update_time >= 1.5 or downloaded == total_length:
                    last_update_time = now
                    elapsed_time = now - start_time
                    speed = downloaded / elapsed_time if elapsed_time > 0 else 0
                    eta = (total_length - downloaded) / speed if speed > 0 and total_length > 0 else 0
                    
                    if progress_callback:
                        progress_callback(downloaded, total_length, speed, eta)

async def fetch_video(url: str, output_file: str, progress_callback):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, download_file_with_progress, url, output_file, progress_callback)
