import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(BASE_DIR, "data", "ig_trade_scorecards.json")
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

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def upsert_scorecard(deal_id, payload):
    data = _load()
    items = data.get("items", [])
    row = None
    for x in items:
        if x.get("deal_id") == deal_id:
            row = x
            break

    if row is None:
        row = {"deal_id": deal_id, "created_at": _now()}
        items.append(row)

    row.update(payload)
    row["updated_at"] = _now()
    data["items"] = items[-3000:]
    _save(data)
    return row

def get_scorecard(deal_id):
    data = _load()
    for x in data.get("items", []):
        if x.get("deal_id") == deal_id:
            return x
    return None

def all_scorecards():
    return _load().get("items", [])

def summarize_scorecards():
    items = all_scorecards()

    complete = [x for x in items if x.get("outcome_state") in ("WIN", "LOSS", "SCRATCH")]
    wins = [x for x in complete if x.get("outcome_state") == "WIN"]
    losses = [x for x in complete if x.get("outcome_state") == "LOSS"]
    scratches = [x for x in complete if x.get("outcome_state") == "SCRATCH"]

    total_realized = sum(_safe_float(x.get("realized_pnl_points", 0.0)) for x in complete)

    return {
        "scorecard_count": len(items),
        "completed_count": len(complete),
        "wins": len(wins),
        "losses": len(losses),
        "scratches": len(scratches),
        "win_rate_pct": round((len(wins) / len(complete) * 100.0), 2) if complete else 0.0,
        "total_realized_pnl_points": round(total_realized, 2),
        "latest_items": items[-20:]
    }
