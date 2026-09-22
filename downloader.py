import os
import asyncio
from playwright.async_api import async_playwright
import yt_dlp

async def get_cloudflare_cookies(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(5)
        
        cookies = await context.cookies()
        user_agent = await page.evaluate("navigator.userAgent")
        
        await browser.close()
        
        cookie_header = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        return cookie_header, user_agent

def download_video_stream(url: str, cookie_header: str, user_agent: str, output_path: str):
    ydl_opts = {
        'outtmpl': output_path,
        'http_headers': {
            'User-Agent': user_agent,
            'Cookie': cookie_header,
            'Referer': 'https://shahidtv.net/',
        },
        'extractor_args': {
            'generic': ['impersonate']
        },
        'concurrent_fragment_downloads': 5,
        'quiet': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

async def fetch_video(url: str, output_file: str):
    cookie_header, user_agent = await get_cloudflare_cookies(url)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, download_video_stream, url, cookie_header, user_agent, output_file)
