import asyncio
from curl_cffi import requests

def download_file(url: str, output_path: str):
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

    # استخدام محاكاة متصفح Chrome لتجاوز TLS Fingerprint الخاصة بـ Cloudflare
    r = requests.get(
        url,
        headers=headers,
        impersonate="chrome124",
        stream=True,
        timeout=300
    )
    
    r.raise_for_status()

    # كتابة بيانات الفيديو على أجزاء لمنع استهلاك الذاكرة
    with open(output_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

async def fetch_video(url: str, output_file: str):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, download_file, url, output_file)
