import os
import sys
import time
import datetime
import subprocess

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

def main():
    if WAIT_FOR_10AM:
        wait_until_hk_10am()

    os.makedirs("recordings", exist_ok=True)
    hk_now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    date_title = hk_now.strftime("%Y-%m-%d")
    file_stamp = hk_now.strftime("%Y-%m-%d_%H%M")
    output_file = f"recordings/903_{file_stamp}.m4a"

    # 商台 叱咤903 (Channel 2) 官方穩定直播串流網址
    m3u8_url = "https://stream.881903.com/live/ch2_hi/playlist.m3u8"

    print(f"[開始錄音] 正在直接錄製直播串流 -> {output_file}")
    print(f"[串流網址] {m3u8_url}")

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
