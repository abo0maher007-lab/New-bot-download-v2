import asyncio
import yt_dlp

def download_with_ytdlp(url: str, output_path: str):
    ydl_opts = {
        'outtmpl': output_path,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
            'Referer': 'https://shahidtv.net/',
            'Origin': 'https://shahidtv.net',
        },
        # توجيه yt-dlp لاستخدام محاكاة المتصفح والتنكر لتجاوز Cloudflare
        'extractor_args': {
            'generic': ['impersonate=chrome']
        },
        'concurrent_fragment_downloads': 5,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

async def fetch_video(url: str, output_file: str):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, download_with_ytdlp, url, output_file)
