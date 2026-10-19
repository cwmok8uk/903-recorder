import os
import sys
import time
import datetime
import subprocess
from playwright.sync_api import sync_playwright

WAIT_FOR_10AM = os.environ.get("WAIT_FOR_10AM", "true").lower() == "true"

def get_record_seconds():
    hk_tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(hk_tz)
    
    # 手動測試模式（於 GitHub 點擊 Run workflow 時）直接回傳自訂秒數
    if not WAIT_FOR_10AM:
        return int(os.environ.get("RECORD_SECONDS", "60"))
        
    # 目標結束時間為香港時間 12:01:00
    end_time = now.replace(hour=12, minute=1, second=0, microsecond=0)
    
    # 1. 嚴重遲到防呆：如果已經過咗 12:01，直接放棄錄音
    if now >= end_time:
        print(f"[嚴重錯誤] 現時為香港時間 {now.strftime('%H:%M:%S')}。已經過咗 12:00 節目時間，為免錄錯節目，取消本次錄音！")
        sys.exit(1)
        
    # 2. 準時喚醒：等到 09:59:30 準備開始
    start_time = now.replace(hour=9, minute=59, second=30, microsecond=0)
    if now < start_time:
        wait_sec = (start_time - now).total_seconds()
        print(f"[等待中] 距離香港時間 09:59:30 仲有 {int(wait_sec)} 秒...")
        time.sleep(wait_sec)
        now = datetime.datetime.now(hk_tz)
        
    # 3. 計算由當前到 12:01 仲剩幾多秒需要錄製
    record_sec = (end_time - now).total_seconds()
    return int(record_sec)

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
    remaining_seconds = get_record_seconds()

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

    attempt_count = 1

    # 智能接力迴圈
    while remaining_seconds > 0:
        if attempt_count == 1:
            output_file = f"recordings/903_{file_stamp}.m4a"
        else:
            output_file = f"recordings/903_{file_stamp}_part{attempt_count}.m4a"

        print(f"\n[開始錄音] 預計錄製剩餘 {int(remaining_seconds)} 秒 -> 檔案: {output_file}")

        cmd = [
            "ffmpeg", "-y",
            "-headers", headers,
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-i", m3u8_url,
            "-t", str(int(remaining_seconds)),
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
            break 
        except subprocess.CalledProcessError as e:
            elapsed = time.time() - start_time
            print(f"[警告] 錄音中途因故中斷（已錄了 {int(elapsed)} 秒），準備自動無縫接力...")
            remaining_seconds -= elapsed
            attempt_count += 1
            time.sleep(3) 

    print(f"\n[大功告成] 錄音任務全數圓滿結束！")

if __name__ == "__main__":
    main()
