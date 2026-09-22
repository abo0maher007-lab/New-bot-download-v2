import asyncio
from curl_cffi import requests

def download_file_with_curl(url: str, output_path: str):
    """
    تحميل الفيديو باستخدام curl_cffi للمرور من حماية Cloudflare TLS Fingerprint
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
        'Referer': 'https://shahidtv.net/',
        'Origin': 'https://shahidtv.net',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'video',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
    }

    # إرسال طلب بحجم القطع Streaming للتأكد من المحاكاة
    with requests.get(url, headers=headers, impersonate="chrome120", stream=True, timeout=120) as response:
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):  # تحميل 1MB في كل دورة
                if chunk:
                    f.write(chunk)

async def fetch_video(url: str, output_file: str):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, download_file_with_curl, url, output_file)
