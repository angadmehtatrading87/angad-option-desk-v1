import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(BASE_DIR, "data", "ig_preopen_action_cooldown.json")
DXB = ZoneInfo("Asia/Dubai")

def _now_dt():
    return datetime.now(DXB)

def _now():
    return _now_dt().isoformat()

def _load():
    if not os.path.exists(PATH):
        return {
            "created_at": _now(),
            "updated_at": _now(),
            "cooldown_until": None,
            "last_action_type": None,
            "last_stage": None,
        }
    try:
        with open(PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {
            "created_at": _now(),
            "updated_at": _now(),
            "cooldown_until": None,
            "last_action_type": None,
            "last_stage": None,
        }

def _save(data):
    data["updated_at"] = _now()
    with open(PATH, "w") as f:
        json.dump(data, f, indent=2)

def get_preopen_cooldown():
    data = _load()
    active = False
    remaining_seconds = 0
    until = data.get("cooldown_until")
    if until:
        try:
            dt = datetime.fromisoformat(until)
            diff = (dt - _now_dt()).total_seconds()
            if diff > 0:
                active = True
                remaining_seconds = int(diff)
        except Exception:
            pass
    return {
        **data,
        "active": active,
        "remaining_seconds": remaining_seconds,
    }

def set_preopen_cooldown(minutes=10, action_type=None, stage=None):
    data = _load()
    until = _now_dt() + timedelta(minutes=minutes)
    data["cooldown_until"] = until.isoformat()
    data["last_action_type"] = action_type
    data["last_stage"] = stage
    _save(data)
    return get_preopen_cooldown()

def clear_preopen_cooldown():
    data = _load()
    data["cooldown_until"] = None
    _save(data)
    return get_preopen_cooldown()
