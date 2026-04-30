import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ig_session_intelligence import get_ig_session_state

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_PATH = os.path.join(BASE_DIR, "data", "ig_learning_memory.json")
DXB = ZoneInfo("Asia/Dubai")

def _now():
    return datetime.now(DXB)

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def _load():
    if not os.path.exists(MEMORY_PATH):
        return {
            "created_at": _now().isoformat(),
            "updated_at": _now().isoformat(),
            "trades": [],
            "daily_reviews": []
        }
    try:
        with open(MEMORY_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {
            "created_at": _now().isoformat(),
            "updated_at": _now().isoformat(),
            "trades": [],
            "daily_reviews": []
        }

def _save(data):
    data["updated_at"] = _now().isoformat()
    with open(MEMORY_PATH, "w") as f:
        json.dump(data, f, indent=2)

def log_trade_memory(event_type, payload):
    data = _load()
    row = {
        "timestamp": _now().isoformat(),
        "event_type": event_type,
        "session_state": get_ig_session_state(),
        **payload
    }
    data.setdefault("trades", []).append(row)
    data["trades"] = data["trades"][-2000:]
    _save(data)
    return row

def summarize_memory():
    data = _load()
    trades = data.get("trades", [])

    by_symbol = {}
    by_session = {}
    by_weekday = {}

    for t in trades:
        symbol = t.get("epic") or t.get("symbol") or "UNKNOWN"
        session = ((t.get("session_state") or {}).get("session")) or "unknown"
        weekday = ((t.get("session_state") or {}).get("weekday"))
        pnl = _safe_float(t.get("pnl_points", t.get("realized_pnl", 0.0)))
        win = 1 if pnl > 0 else 0

        if symbol not in by_symbol:
            by_symbol[symbol] = {"count": 0, "wins": 0, "pnl": 0.0}
        if session not in by_session:
            by_session[session] = {"count": 0, "wins": 0, "pnl": 0.0}
        if weekday not in by_weekday:
            by_weekday[weekday] = {"count": 0, "wins": 0, "pnl": 0.0}

        by_symbol[symbol]["count"] += 1
        by_symbol[symbol]["wins"] += win
        by_symbol[symbol]["pnl"] += pnl

        by_session[session]["count"] += 1
        by_session[session]["wins"] += win
        by_session[session]["pnl"] += pnl

        by_weekday[weekday]["count"] += 1
        by_weekday[weekday]["wins"] += win
        by_weekday[weekday]["pnl"] += pnl

    return {
        "trade_count": len(trades),
        "by_symbol": by_symbol,
        "by_session": by_session,
        "by_weekday": by_weekday,
        "recent_trades": trades[-20:]
    }

def write_daily_review(review_payload):
    data = _load()
    row = {
        "timestamp": _now().isoformat(),
        "date": _now().date().isoformat(),
        **review_payload
    }
    data.setdefault("daily_reviews", []).append(row)
    data["daily_reviews"] = data["daily_reviews"][-365:]
    _save(data)
    return row

def latest_daily_review():
    data = _load()
    reviews = data.get("daily_reviews", [])
    return reviews[-1] if reviews else {}
