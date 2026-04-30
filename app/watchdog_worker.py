import os
import time
import subprocess
import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

CHECK_INTERVAL_SECONDS = 30
SYSTEMCTL = "/bin/systemctl"

SERVICES = [
    "angad-option-desk",
    "angad-prep-worker",
    "angad-autonomous-execution",
    "angad-virtual-monitor",
    "angad-daily-summary",
    "angad-news-macro",
    "angad-owner-reporting",
    "angad-learning-worker",
    "angad-adaptive-learning",
    "angad-ig-execution",
    "angad-ig-pnl-reporter",
    "angad-daily-objective",
    "nginx",
]

URLS = [
    "http://127.0.0.1/",
    "http://127.0.0.1/virtual-portfolio",
    "http://127.0.0.1/virtual-monitor",
    "http://127.0.0.1/news-macro",
]

WEB_USERNAME = os.getenv("APP_USERNAME") or os.getenv("BASIC_AUTH_USERNAME") or ""
WEB_PASSWORD = os.getenv("APP_PASSWORD") or os.getenv("BASIC_AUTH_PASSWORD") or ""

def run_cmd(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def service_is_active(service: str):
    r = run_cmd([SYSTEMCTL, "is-active", service])
    return r.returncode == 0 and r.stdout.strip() == "active"

def restart_service(service: str):
    run_cmd([SYSTEMCTL, "restart", service])

def url_ok(url: str):
    try:
        auth = (WEB_USERNAME, WEB_PASSWORD) if WEB_USERNAME and WEB_PASSWORD else None
        r = requests.get(url, timeout=8, auth=auth)
        return r.status_code == 200
    except Exception:
        return False

def main():
    while True:
        try:
            for service in SERVICES:
                if not service_is_active(service):
                    restart_service(service)
            for url in URLS:
                _ = url_ok(url)
            time.sleep(CHECK_INTERVAL_SECONDS)
        except Exception:
            time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
