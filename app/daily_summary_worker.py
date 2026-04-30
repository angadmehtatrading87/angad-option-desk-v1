import time
from datetime import datetime
from zoneinfo import ZoneInfo

from app.telegram_alerts import send_telegram_message
from app.daily_summary import build_start_of_day_summary, build_end_of_day_summary

DXB = ZoneInfo("Asia/Dubai")

last_start_sent_for = None
last_end_sent_for = None

def now_dxb():
    return datetime.now(DXB)

def should_send_start(now):
    return now.hour == 8 and now.minute == 0

def should_send_end(now):
    return now.hour == 23 and now.minute == 45

def main():
    global last_start_sent_for, last_end_sent_for

    send_telegram_message("📬 Daily summary worker restarted.")

    while True:
        try:
            now = now_dxb()
            today = now.date().isoformat()

            if should_send_start(now) and last_start_sent_for != today:
                send_telegram_message(build_start_of_day_summary())
                last_start_sent_for = today

            if should_send_end(now) and last_end_sent_for != today:
                send_telegram_message(build_end_of_day_summary())
                last_end_sent_for = today

            time.sleep(30)

        except Exception as e:
            send_telegram_message(f"Daily summary worker error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
