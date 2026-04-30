import os
import yaml
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_window_config():
    with open(os.path.join(BASE_DIR, "config", "trading_window.yaml"), "r") as f:
        return yaml.safe_load(f)

def now_local():
    cfg = load_window_config()
    tz = ZoneInfo(cfg.get("timezone", "Asia/Dubai"))
    return datetime.now(tz)

def is_weekday():
    return now_local().weekday() < 5

def in_window(section_name):
    cfg = load_window_config()
    section = cfg.get(section_name, {})

    if not section.get("enabled", True):
        return False, f"{section_name} disabled"

    if not is_weekday():
        return False, "Weekend"

    now = now_local()
    now_minutes = now.hour * 60 + now.minute

    start_minutes = int(section.get("start_hour", 0)) * 60 + int(section.get("start_minute", 0))
    end_minutes = int(section.get("end_hour", 23)) * 60 + int(section.get("end_minute", 59))

    if start_minutes <= now_minutes <= end_minutes:
        return True, f"Inside {section_name}"

    return False, f"Outside {section_name}"

def can_open_new_option_trade():
    cfg = load_window_config()
    rules = cfg.get("rules", {})

    if rules.get("allow_new_option_trades_only_in_us_window", True):
        return in_window("us_options_window_dubai")

    return True, "New trades allowed by config"

def trading_window_status():
    return {
        "now_dubai": now_local().isoformat(),
        "weekday": is_weekday(),
        "morning_macro_window": in_window("morning_macro_window"),
        "us_options_window_dubai": in_window("us_options_window_dubai"),
        "position_monitor_window_dubai": in_window("position_monitor_window_dubai"),
        "can_open_new_option_trade": can_open_new_option_trade(),
        "config": load_window_config()
    }
