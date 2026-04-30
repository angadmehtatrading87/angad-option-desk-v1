import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

DXB = ZoneInfo("Asia/Dubai")
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PATH = os.path.join(DATA_DIR, "ig_exit_registry.json")


def _now_iso():
    return datetime.now(DXB).isoformat()


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load():
    _ensure_dir()
    if not os.path.exists(PATH):
        return {"positions": {}, "recent_exits": {}}
    try:
        with open(PATH, "r") as f:
            data = json.load(f)
            if isinstance(data, dict):
                data.setdefault("positions", {})
                data.setdefault("recent_exits", {})
                return data
    except Exception:
        pass
    return {"positions": {}, "recent_exits": {}}


def _save(data):
    _ensure_dir()
    with open(PATH, "w") as f:
        json.dump(data, f, indent=2)


def _position_key(position):
    deal_id = (position or {}).get("deal_id") or (position or {}).get("dealId")
    epic = (position or {}).get("epic")
    direction = (position or {}).get("direction")
    if deal_id:
        return f"deal::{deal_id}"
    return f"{epic}::{direction}"


def get_position_record(position):
    data = _load()
    return (data.get("positions") or {}).get(_position_key(position), {})


def update_position_record(position, updates):
    data = _load()
    key = _position_key(position)
    existing = (data.get("positions") or {}).get(key, {})
    existing.update(updates or {})
    existing["updated_at"] = _now_iso()
    data["positions"][key] = existing
    _save(data)
    return existing


def delete_position_record(position):
    data = _load()
    key = _position_key(position)
    if key in data.get("positions", {}):
        del data["positions"][key]
        _save(data)


def record_peak_profit(position, pnl_points):
    rec = get_position_record(position)
    prev_peak = float(rec.get("peak_pnl_points", 0.0) or 0.0)
    pnl_points = float(pnl_points or 0.0)
    if pnl_points > prev_peak:
        return update_position_record(position, {"peak_pnl_points": pnl_points})
    return rec


def record_exit_event(position, reason, pnl_points=None, cooldown_minutes=20):
    data = _load()
    key = _position_key(position)
    now = datetime.now(DXB)
    cooldown_until = now.timestamp() + (cooldown_minutes * 60)

    data["recent_exits"][key] = {
        "epic": (position or {}).get("epic"),
        "direction": (position or {}).get("direction"),
        "reason": reason,
        "pnl_points": pnl_points,
        "closed_at": now.isoformat(),
        "reentry_cooldown_until_ts": cooldown_until,
    }

    if key in data.get("positions", {}):
        del data["positions"][key]

    _save(data)
    return data["recent_exits"][key]


def get_recent_exit(position):
    data = _load()
    return (data.get("recent_exits") or {}).get(_position_key(position), {})


def get_reentry_state(position):
    rec = get_recent_exit(position)
    if not rec:
        return {
            "reentry_allowed": True,
            "cooldown_active": False,
            "remaining_seconds": 0,
            "reason": "no_recent_exit",
        }

    now_ts = datetime.now(DXB).timestamp()
    until_ts = float(rec.get("reentry_cooldown_until_ts", 0.0) or 0.0)
    remaining = int(max(0, until_ts - now_ts))

    return {
        "reentry_allowed": remaining <= 0,
        "cooldown_active": remaining > 0,
        "remaining_seconds": remaining,
        "reason": rec.get("reason") or "recent_exit_cooldown",
    }
