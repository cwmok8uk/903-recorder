import os
import sys
import time
import datetime
import subprocess
from playwright.sync_api import sync_playwright

TOTAL_SECONDS = int(os.environ.get("RECORD_SECONDS", "7260"))  # 目標總長度約 2 小時零 1 分鐘
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

def get_stream_info():
    m3u8_url = None
    cookies_str = ""
    user_agent = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        def handle_request(request):
            nonlocal m3u8_url
            if ".m3u8" in request.url and not m3u8_url:
                m3u8_url = request.url
                print(f"[成功捕捉 m3u8] {m3u8_url}")

        page.on("request", handle_request)
        
        print("[瀏覽器] 正在打開商台直播主頁...")
        try:
            page.goto("https://www.881903.com/live/903", wait_until="domcontentloaded", timeout=60000)
        except Exception:
            pass

        for _ in range(12):
            if m3u8_url:
                break
            try:
                page.evaluate("""() => {
                    document.querySelectorAll('button, a').forEach(el => {
                        if (el.innerText && (el.innerText.includes('同意') || el.innerText.includes('關閉'))) el.click();
                    });
                    const btn = document.querySelector('[class*="play"], button');
                    if (btn) btn.click();
                }""")
            except Exception:
                pass
            page.wait_for_timeout(2000)

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

    print("[動態尋找] 正在獲取串流網址與驗證 Cookie...")
    m3u8_url, cookies_str, user_agent = get_stream_info()

    if not m3u8_url:
        print("[警告] 動態捕捉未成功，使用備用串流...")
        m3u8_url = "https://live-s.881903.com/edge-aac/903hd/playlist.m3u8"
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    headers = f"Referer: https://www.881903.com/\r\nUser-Agent: {user_agent}\r\n"
    if cookies_str:
        headers += f"Cookie: {cookies_str}\r\n"

    remaining_seconds = TOTAL_SECONDS
    attempt_count = 1

    # 智能接力迴圈：只要未錄夠總秒數，就會一直保持/重啟錄音
    while remaining_seconds > 0:
        if attempt_count == 1:
            output_file = f"recordings/903_{file_stamp}.m4a"
        else:
            output_file = f"recordings/903_{file_stamp}_part{attempt_count}.m4a"

        print(f"\n[開始錄音] 預計錄製剩餘 {remaining_seconds} 秒 -> 檔案: {output_file}")

        cmd = [
            "ffmpeg", "-y",
            "-headers", headers,
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-i", m3u8_url,
            "-t", str(remaining_seconds),
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            "-metadata", f"title=叱咤903重溫 {date_title}",
            "-metadata", "artist=叱咤903",
            "-metadata", "album=我的903私人重溫",
            output_file
        ]

        start_time = time.time()
        try:
            subprocess.run(cmd, check=True)
            print(f"[完成] 本段錄音順利完成！")
            break # 順利完成就直接跳出迴圈
        except subprocess.CalledProcessError as e:
            elapsed = time.time() - start_time
            print(f"[警告] 錄音中途因故中斷（已錄了 {int(elapsed)} 秒），準備自動無縫接力...")
            remaining_seconds -= int(elapsed)
            attempt_count += 1
            time.sleep(3) # 稍微抖動冷卻後自動重開新檔接力

    print(f"\n[大功告成] 錄音任務全數圓滿結束！")

if __name__ == "__main__":
    main()
