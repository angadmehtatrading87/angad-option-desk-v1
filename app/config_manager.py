import os
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_config(filename):
    path = os.path.join(BASE_DIR, "config", filename)
    with open(path, "r") as f:
        return yaml.safe_load(f)

def save_config(filename, data):
    path = os.path.join(BASE_DIR, "config", filename)
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False)

def set_kill_switch(value: bool):
    risk = load_config("risk_limits.yaml")
    risk["kill_switch"] = value
    save_config("risk_limits.yaml", risk)
    return risk

def set_scanner_enabled(value: bool):
    schedule = load_config("schedule.yaml")
    schedule["scheduled_scanner_enabled"] = value
    save_config("schedule.yaml", schedule)
    return schedule
