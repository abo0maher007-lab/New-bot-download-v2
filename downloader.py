import asyncio
from curl_cffi import requests

def download_file_with_curl(url: str, output_path: str):
    """
    تحميل الفيديو باستخدام curl_cffi مع معالجة الاستجابة بشكل صحيح
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'ar,en-US;q=0.7,en;q=0.3',
        'Referer': 'https://shahidtv.net/',
        'Sec-Fetch-Dest': 'video',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'cross-site',
    }

    # إرسال الطلب المباشر محاكياً متصفح كروم 120
    response = requests.get(
        url, 
        headers=headers, 
        impersonate="chrome120", 
        stream=True, 
        timeout=180
    )
    
    # التحقق من أن الاستجابة ناجحة (رمز 200)
    response.raise_for_status()

    # كتابة الملف على أجزاء
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=2 * 1024 * 1024):  # قطع بحجم 2 ميجابايت
            if chunk:
                f.write(chunk)

async def fetch_video(url: str, output_file: str):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, download_file_with_curl, url, output_file)
