import os
import sys
import time
import datetime
import subprocess
from playwright.sync_api import sync_playwright

# 錄音長度：預設 7260 秒 (2小時零1分鐘，確保頭尾唔會漏)
RECORD_SECONDS = int(os.environ.get("RECORD_SECONDS", "7260"))
WAIT_FOR_10AM = os.environ.get("WAIT_FOR_10AM", "true").lower() == "true"

def wait_until_hk_10am():
    hk_tz = datetime.timezone(datetime.timedelta(hours=8))
    while True:
        now = datetime.datetime.now(hk_tz)
        # 提早喺 09:59:30 開始準備擷取串流
        target = now.replace(hour=9, minute=59, second=30, microsecond=0)
        if now >= target or now.hour >= 10:
            break
        wait_sec = (target - now).total_seconds()
        print(f"[等待中] 距離香港時間 09:59:30 仲有 {int(wait_sec)} 秒...")
        time.sleep(min(wait_sec, 15))

def get_stream_info():
    m3u8_url = None
    cookies_str = ""
    user_agent = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"
        )
        page = context.new_page()

        def handle_request(request):
            nonlocal m3u8_url
            if ".m3u8" in request.url and ("903" in request.url or "chunk" in request.url or "playlist" in request.url):
                m3u8_url = request.url

        page.on("request", handle_request)
        print("[瀏覽器] 正在打開 881903.com 擷取直播串流...")
        page.goto("https://www.881903.com/live/903", wait_until="domcontentloaded", timeout=60000)

        for _ in range(20):
            if m3u8_url:
                break
            try:
                page.locator("button, .play, [class*='play']").first.click(timeout=2000)
            except Exception:
                pass
            page.wait_for_timeout(1000)

        user_agent = page.evaluate("navigator.userAgent")
        cookies = context.cookies()
        cookies_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        browser.close()

    return m3u8_url, cookies_str, user_agent

def main():
    if WAIT_FOR_10AM:
        wait_until_hk_10am()

    os.makedirs("recordings", exist_ok=True)
    hk_now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    date_title = hk_now.strftime("%Y-%m-%d")
    file_stamp = hk_now.strftime("%Y-%m-%d_%H%M")
    output_file = f"recordings/903_{file_stamp}.m4a"

    # 嘗試最多 3 次擷取串流，確保穩定
    m3u8_url, cookies_str, user_agent = None, "", ""
    for attempt in range(3):
        m3u8_url, cookies_str, user_agent = get_stream_info()
        if m3u8_url:
            break
        print(f"[重試] 第 {attempt+1} 次擷取失敗，5 秒後重試...")
        time.sleep(5)

    if not m3u8_url:
        print("[錯誤] 無法擷取 m3u8 串流網址！")
        sys.exit(1)

    print(f"[開始錄音] 正在錄製 {RECORD_SECONDS} 秒 -> {output_file}")
    headers = f"Referer: https://www.881903.com/\r\nUser-Agent: {user_agent}\r\n"
    if cookies_str:
        headers += f"Cookie: {cookies_str}\r\n"

    cmd = [
        "ffmpeg", "-y",
        "-headers", headers,
        "-i", m3u8_url,
        "-t", str(RECORD_SECONDS),
        "-c", "copy",
        "-bsf:a", "aac_adtstoasc",
        "-metadata", f"title=叱咤903 節目重溫 ({date_title})",
        "-metadata", "artist=叱咤903",
        "-metadata", "album=我的903私人重溫",
        output_file
    ]

    subprocess.run(cmd, check=True)
    print(f"[完成] 錄音成功：{output_file}")

if __name__ == "__main__":
    main()
