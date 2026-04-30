import time
import os
from datetime import datetime, timezone
import yaml

from app.market_scanner import run_scan
from app.telegram_alerts import send_telegram_message

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def is_market_window():
    cfg = load_yaml(os.path.join(BASE_DIR, "config", "schedule.yaml"))

    now = datetime.now(timezone.utc)

    if cfg.get("weekdays_only", True):
        # Monday = 0, Sunday = 6
        if now.weekday() > 4:
            return False, "Weekend"

    hours = cfg.get("market_hours_utc", {})
    start_hour = int(hours.get("start_hour", 13))
    start_minute = int(hours.get("start_minute", 30))
    end_hour = int(hours.get("end_hour", 21))
    end_minute = int(hours.get("end_minute", 0))

    start_minutes = start_hour * 60 + start_minute
    end_minutes = end_hour * 60 + end_minute
    now_minutes = now.hour * 60 + now.minute

    if start_minutes <= now_minutes <= end_minutes:
        return True, "Within market window"

    return False, "Outside market window"

def main():
    cfg = load_yaml(os.path.join(BASE_DIR, "config", "schedule.yaml"))
    interval_minutes = int(cfg.get("scan_interval_minutes", 30))

    send_telegram_message(
        f"🤖 Scheduled scanner started. Interval: {interval_minutes} minutes. Simulation mode only."
    )

    while True:
        try:
            cfg = load_yaml(os.path.join(BASE_DIR, "config", "schedule.yaml"))

            if not cfg.get("scheduled_scanner_enabled", True):
                time.sleep(60)
                continue

            allowed, reason = is_market_window()

            if allowed:
                created = run_scan()

                if created:
                    send_telegram_message(
                        f"📡 Scheduled scan completed. Created {len(created)} proposal(s)."
                    )
                else:
                    send_telegram_message(
                        "📡 Scheduled scan completed. No qualifying setup found."
                    )
            else:
                # Quiet outside market hours to avoid spam.
                pass

            time.sleep(interval_minutes * 60)

        except Exception as e:
            send_telegram_message(f"Scheduled scanner error: {e}")
            time.sleep(300)

if __name__ == "__main__":
    main()
