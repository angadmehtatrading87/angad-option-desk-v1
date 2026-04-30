import subprocess
import os
import yaml
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SERVICES = [
    "angad-option-desk",
    "angad-telegram-worker",
    "angad-scheduled-scanner",
    "nginx"
]

def service_status(service_name):
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip()
    except Exception as e:
        return f"error: {e}"

def load_yaml_file(filename):
    path = os.path.join(BASE_DIR, "config", filename)
    with open(path, "r") as f:
        return yaml.safe_load(f)

def get_system_health():
    risk = load_yaml_file("risk_limits.yaml")
    schedule = load_yaml_file("schedule.yaml")

    services = {s: service_status(s) for s in SERVICES}

    return {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "services": services,
        "kill_switch": risk.get("kill_switch"),
        "auto_trade_enabled": risk.get("auto_trade_enabled"),
        "account_mode": risk.get("account_mode"),
        "scheduled_scanner_enabled": schedule.get("scheduled_scanner_enabled"),
        "scan_interval_minutes": schedule.get("scan_interval_minutes"),
        "broker_connected": False,
        "execution_mode": "simulation_only"
    }
