import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(BASE_DIR, "data", "ig_throttle_guard.json")
DXB = ZoneInfo("Asia/Dubai")

def _now():
    return datetime.now(DXB)

def _load():
    if not os.path.exists(STATE_PATH):
        return {
            "created_at": _now().isoformat(),
            "updated_at": _now().isoformat(),
            "cooldown_until": None,
            "last_reason": None,
            "flatten_pending": False,
            "flatten_pending_since": None,
        }
    try:
        with open(STATE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {
            "created_at": _now().isoformat(),
            "updated_at": _now().isoformat(),
            "cooldown_until": None,
            "last_reason": None,
            "flatten_pending": False,
            "flatten_pending_since": None,
        }

def _save(data):
    data["updated_at"] = _now().isoformat()
    with open(STATE_PATH, "w") as f:
        json.dump(data, f, indent=2)

def set_throttle_cooldown(minutes=15, reason="api_throttled"):
    data = _load()
    data["cooldown_until"] = (_now() + timedelta(minutes=minutes)).isoformat()
    data["last_reason"] = reason
    _save(data)
    return data

def clear_throttle():
    data = _load()
    data["cooldown_until"] = None
    data["last_reason"] = None
    _save(data)
    return data

def throttle_status():
    data = _load()
    until = data.get("cooldown_until")
    active = False
    remaining_seconds = 0

    if until:
        try:
            dt = datetime.fromisoformat(until)
            delta = (dt - _now()).total_seconds()
            if delta > 0:
                active = True
                remaining_seconds = int(delta)
        except Exception:
            active = False

    return {
        **data,
        "active": active,
        "remaining_seconds": remaining_seconds
    }

def mark_flatten_pending(flag=True):
    data = _load()
    data["flatten_pending"] = bool(flag)
    data["flatten_pending_since"] = _now().isoformat() if flag else None
    _save(data)
    return data
