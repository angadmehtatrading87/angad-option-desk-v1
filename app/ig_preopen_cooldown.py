import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(BASE_DIR, "data", "ig_preopen_cooldown.json")
DXB = ZoneInfo("Asia/Dubai")

def _now_dt():
    return datetime.now(DXB)

def _now():
    return _now_dt().isoformat()

def _load():
    if not os.path.exists(PATH):
        return {"created_at": _now(), "updated_at": _now(), "cooldown_until": None, "last_action_type": None}
    try:
        with open(PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {"created_at": _now(), "updated_at": _now(), "cooldown_until": None, "last_action_type": None}

def _save(data):
    data["updated_at"] = _now()
    with open(PATH, "w") as f:
        json.dump(data, f, indent=2)

def set_cooldown(seconds, action_type=None):
    data = _load()
    until = _now_dt() + timedelta(seconds=int(seconds or 0))
    data["cooldown_until"] = until.isoformat()
    data["last_action_type"] = action_type
    _save(data)
    return data

def cooldown_status():
    data = _load()
    until_raw = data.get("cooldown_until")
    if not until_raw:
        return {
            **data,
            "active": False,
            "remaining_seconds": 0,
        }
    try:
        until = datetime.fromisoformat(until_raw)
    except Exception:
        return {
            **data,
            "active": False,
            "remaining_seconds": 0,
        }
    remaining = int((until - _now_dt()).total_seconds())
    return {
        **data,
        "active": remaining > 0,
        "remaining_seconds": max(0, remaining),
    }

def clear_cooldown():
    data = _load()
    data["cooldown_until"] = None
    data["last_action_type"] = None
    _save(data)
    return data
