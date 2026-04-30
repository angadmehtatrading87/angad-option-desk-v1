import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(BASE_DIR, "data", "ig_decision_audit.json")
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

def add_decision_audit(item):
    data = _load()
    items = data.get("items", [])
    row = {
        "timestamp": _now(),
        **(item or {})
    }
    items.append(row)
    data["items"] = items[-5000:]
    _save(data)
    return row

def list_decision_audits(limit=50):
    data = _load()
    return data.get("items", [])[-int(limit):]

def summarize_decision_audit():
    items = _load().get("items", [])
    latest = items[-200:]

    verdict_counts = {}
    threshold_counts = {}
    blocked = 0
    avg_score = 0.0
    avg_size = 0.0

    for x in latest:
        verdict = str(x.get("deploy_verdict", "UNKNOWN"))
        threshold = str(x.get("threshold_state", "UNKNOWN"))
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        threshold_counts[threshold] = threshold_counts.get(threshold, 0) + 1
        if x.get("should_block"):
            blocked += 1
        avg_score += float(x.get("master_score", 0.0) or 0.0)
        avg_size += float(x.get("final_size_multiplier", 0.0) or 0.0)

    n = len(latest)
    if n > 0:
        avg_score = round(avg_score / n, 2)
        avg_size = round(avg_size / n, 4)

    return {
        "audit_count": len(items),
        "recent_count": n,
        "verdict_counts": verdict_counts,
        "threshold_counts": threshold_counts,
        "blocked_count": blocked,
        "avg_master_score": avg_score,
        "avg_final_size_multiplier": avg_size,
        "latest_items": latest[-20:]
    }
