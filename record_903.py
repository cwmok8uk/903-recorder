import os
import re
import sys
import time
import datetime
import subprocess
from playwright.sync_api import sync_playwright

RECORD_SECONDS = int(os.environ.get("RECORD_SECONDS", "7260"))
WAIT_FOR_10AM = os.environ.get("WAIT_FOR_10AM", "true").lower() == "true"

def wait_until_hk_10am():
    hk_tz = datetime.timezone(datetime.timedelta(hours=8))
    while True:
        now = datetime.datetime.now(hk_tz)
        target = now.replace(hour=9, minute=59, second=30, microsecond=0)
        if now >= target or now.hour >= 10:
            break
        wait_sec = (target - now).total_seconds()
        print(f"[等待中] 距離香港時間 09:59:30 仲有 {int(wait_sec)} 秒...")
        time.sleep(min(wait_sec, 15))

def get_stream_from_browser():
    m3u8_url = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        def handle_request(request):
            nonlocal m3u8_url
            if ".m3u8" in request.url:
                m3u8_url = request.url
                print(f"[捕捉到 m3u8] {m3u8_url}")

        page.on("request", handle_request)
        
        print("[瀏覽器] 正在打開商台直播主頁...")
        try:
            page.goto("https://www.881903.com/live/903", wait_until="domcontentloaded", timeout=60000)
        except Exception:
            pass

        # 自動嘗試點擊播放掣或切換頻道以激發串流載入
        for _ in range(10):
            if m3u8_url:
                break
            try:
                page.evaluate("""() => {
                    // 點擊同意 Cookie
                    document.querySelectorAll('button, a').forEach(el => {
                        if (el.innerText && (el.innerText.includes('同意') || el.innerText.includes('關閉'))) el.click();
                    });
                    // 點擊播放按鈕
                    const btn = document.querySelector('[class*="play"], button, [class*="player"]');
                    if (btn) btn.click();
                }""")
            except Exception:
                pass
            page.wait_for_timeout(2000)

        browser.close()
    return m3u8_url

def main():
    if WAIT_FOR_10AM:
        wait_until_hk_10am()

    os.makedirs("recordings", exist_ok=True)
    hk_now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    date_title = hk_now.strftime("%Y-%m-%d")
    file_stamp = hk_now.strftime("%Y-%m-%d_%H%M")
    output_file = f"recordings/903_{file_stamp}.m4a"

    print("[動態尋找] 正在獲取當刻最新的直播串流網址...")
    m3u8_url = get_stream_from_browser()

    # 如果動態捉唔到，退一步使用備用串流格式
    if not m3u8_url:
        print("[警告] 動態捕捉未成功，使用備用串流通道...")
        m3u8_url = "https://stream.881903.com/live/ch2/playlist.m3u8"

    print(f"[開始錄音] 串流網址: {m3u8_url}")
    print(f"[目標檔案] {output_file}")

    cmd = [
        "ffmpeg", "-y",
        "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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
