import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(BASE_DIR, "data", "ig_preopen_action_registry.json")
DXB = ZoneInfo("Asia/Dubai")

def _now():
    return datetime.now(DXB).isoformat()

def _load():
    if not os.path.exists(PATH):
        return {"created_at": _now(), "updated_at": _now(), "items": []}
    try:
        with open(PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {"created_at": _now(), "updated_at": _now(), "items": []}

def _save(data):
    data["updated_at"] = _now()
    with open(PATH, "w") as f:
        json.dump(data, f, indent=2)

def add_preopen_action(item):
    data = _load()
    row = {"timestamp": _now(), **(item or {})}
    data["items"] = (data.get("items") or [])[-999:] + [row]
    _save(data)
    return row

def list_preopen_actions(limit=50):
    return _load().get("items", [])[-int(limit):]

def summarize_preopen_actions():
    items = _load().get("items", [])
    latest = items[-100:]

    by_action = {}
    by_status = {}

    for x in latest:
        a = str(x.get("action_type", "UNKNOWN"))
        s = str(x.get("status", "UNKNOWN"))
        by_action[a] = by_action.get(a, 0) + 1
        by_status[s] = by_status.get(s, 0) + 1

    return {
        "total_count": len(items),
        "recent_count": len(latest),
        "by_action": by_action,
        "by_status": by_status,
        "latest_items": latest[-20:]
    }
