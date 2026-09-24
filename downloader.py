import time
import os
import asyncio
import re
import urllib.request
from urllib.parse import urlparse
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

def is_youtube_or_supported_site(url: str) -> bool:
    """التحقق مما إذا كان الرابط يخص يوتيوب أو مواقع المنصات الشبيهة"""
    domain = urlparse(url).netloc.lower()
    youtube_domains = ['youtube.com', 'youtu.be', 'm.youtube.com', 'www.youtube.com']
    return any(yd in domain for yd in youtube_domains)

def download_via_ytdlp(url: str, output_path: str, progress_callback, active_proxy: str = None) -> bool:
    """طريقة 1 (الأقوى لليوتيوب والمواقع المقيدة): باستخدام yt-dlp المعزز"""
    print("[yt-dlp] البدء بالتنزيل عبر yt-dlp...")
    
    def ytdlp_hook(d):
        if d['status'] == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            speed = d.get('speed', 0) or 0
            eta = d.get('eta', 0) or 0
            if progress_callback:
                progress_callback(downloaded, total, speed, eta)

    parsed = urlparse(url)
    origin_site = f"{parsed.scheme}://{parsed.netloc}"

    ydl_opts = {
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [ytdlp_hook],
        # توفير دمج وتحديد أفضل جودة متوافقة
        'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
            'Referer': origin_site,
            'Origin': origin_site,
            'Accept': '*/*',
        },
        'impersonate': 'chrome124',
    }

    if active_proxy:
        ydl_opts['proxy'] = active_proxy

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return os.path.exists(output_path) and os.path.getsize(output_path) > 0

def download_via_curl_cffi(url: str, output_path: str, progress_callback, proxies: dict = None) -> bool:
    """طريقة 2 (الأفضل للروابط المباشرة بحماية Cloudflare): عبر curl_cffi بـ chrome124"""
    print("[curl_cffi] البدء بالتنزيل عبر محاكاة البصمة...")
    session = requests.Session(impersonate="chrome124")
    
    parsed = urlparse(url)
    base_domain = f"{parsed.scheme}://{parsed.netloc}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
        'Referer': f"{base_domain}/",
        'Origin': base_domain,
        'Sec-Ch-Ua': '"Chromium";v="128", "Not=A?Brand";v="24", "Google Chrome";v="128"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'video',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site',
    }

    # صافحة أولية للموقع الأساسي لبناء الكوكيز
    try:
        session.get(base_domain, headers={'User-Agent': headers['User-Agent']}, proxies=proxies, timeout=15)
    except Exception as e:
        print(f"[curl_cffi] Handshake skipped: {e}")

    response = session.get(url, headers=headers, stream=True, allow_redirects=True, proxies=proxies, timeout=90)
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

def download_via_urllib(url: str, output_path: str, progress_callback, active_proxy: str = None) -> bool:
    """طريقة 3 (احتياطية خفيفة للروابط المباشرة العادية): عبر urllib القياسية"""
    print("[urllib] البدء بالتنزيل الاحتياطي المباشر...")
    
    req = urllib.request.Request(
        url, 
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    )
    
    opener_args = []
    if active_proxy:
        proxy_handler = urllib.request.ProxyHandler({'http': active_proxy, 'https': active_proxy})
        opener_args.append(proxy_handler)
        
    opener = urllib.request.build_opener(*opener_args)
    
    with opener.open(req, timeout=60) as response, open(output_path, 'wb') as out_file:
        total_length = int(response.getheader('Content-Length', 0))
        downloaded = 0
        start_time = time.time()
        last_update_time = start_time

        while True:
            chunk = response.read(2 * 1024 * 1024)
            if not chunk:
                break
            out_file.write(chunk)
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

def perform_download(url: str, output_path: str, progress_callback, proxy: str = None):
    env_proxy = os.getenv("PROXY_URL", "").strip()
    active_proxy = proxy if (proxy and proxy.strip()) else env_proxy

    proxies = None
    if active_proxy:
        proxies = {
            "http": active_proxy,
            "https": active_proxy
        }

    # إذا كان الرابط يخص يوتيوب، يتم معالجته مباشرة بواسطة yt-dlp
    if is_youtube_or_supported_site(url):
        try:
            if download_via_ytdlp(url, output_path, progress_callback, active_proxy):
                print("تم تحميل فيديو اليوتيوب بنجاح بواسطة yt-dlp.")
                return
        except Exception as e:
            print(f"فشل تنزيل اليوتيوب عبر yt-dlp: {e}")
            if os.path.exists(output_path):
                os.remove(output_path)

    # للروابط الأخرى (مثل shahidtv والمباشرة): تجربة curl_cffi أولاً
    try:
        if download_via_curl_cffi(url, output_path, progress_callback, proxies):
            print("تم التحميل بنجاح بواسطة curl_cffi.")
            return
    except Exception as e:
        print(f"فشلت طريقة curl_cffi: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)

    # المحاولة الثانية: عبر yt-dlp
    try:
        if download_via_ytdlp(url, output_path, progress_callback, active_proxy):
            print("تم التحميل بنجاح بواسطة yt-dlp.")
            return
    except Exception as e:
        print(f"فشلت طريقة yt-dlp: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)

    # المحاولة الثالثة الاحتياطية: عبر urllib القياسية
    try:
        if download_via_urllib(url, output_path, progress_callback, active_proxy):
            print("تم التحميل بنجاح بواسطة urllib.")
            return
    except Exception as e:
        print(f"فشلت طريقة urllib: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)

    raise Exception("فشلت جميع طرق التحميل المتاحة (curl_cffi / yt-dlp / urllib). يرجى التأكد من سلامة الرابط والبروكسي.")

def verify_download(output_path: str) -> bool:
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0

async def fetch_video(url: str, output_file: str, progress_callback, proxy: str = None):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, perform_download, url, output_file, progress_callback, proxy)
