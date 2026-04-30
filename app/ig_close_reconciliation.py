import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ig_api_governor import get_ig_cached_snapshot

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(BASE_DIR, "data", "ig_close_reconciliation.json")
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

def add_pending_close(epic, deal_id, direction, close_size, deal_reference, requested_action, meta=None):
    data = _load()
    items = data.get("items", [])
    existing = None
    for row in items:
        if row.get("deal_id") == deal_id and row.get("status") in ("PENDING_BROKER", "SUBMITTED"):
            existing = row
            break

    if existing:
        existing["updated_at"] = _now()
        if deal_reference:
            existing["deal_reference"] = deal_reference
        _save(data)
        return existing

    row = {
        "created_at": _now(),
        "updated_at": _now(),
        "epic": epic,
        "deal_id": deal_id,
        "direction": direction,
        "close_size": close_size,
        "deal_reference": deal_reference,
        "requested_action": requested_action,
        "status": "SUBMITTED",
        "meta": meta or {}
    }
    items.append(row)
    data["items"] = items[-1000:]
    _save(data)
    return row

def pending_close_for_deal(deal_id):
    data = _load()
    for row in data.get("items", []):
        if row.get("deal_id") == deal_id and row.get("status") in ("SUBMITTED", "PENDING_BROKER"):
            return row
    return None

def all_reconciliation_items():
    data = _load()
    return data.get("items", [])

def reconcile_pending_closes():
    data = _load()
    items = data.get("items", [])
    snap = get_ig_cached_snapshot(force_refresh=True)
    live_positions = ((snap.get("positions") or {}).get("positions") or [])
    live_deal_ids = {p.get("deal_id") for p in live_positions}

    changed = []
    for row in items:
        if row.get("status") not in ("SUBMITTED", "PENDING_BROKER"):
            continue

        deal_id = row.get("deal_id")
        if deal_id in live_deal_ids:
            row["status"] = "PENDING_BROKER"
            row["updated_at"] = _now()
        else:
            row["status"] = "CONFIRMED_CLOSED"
            row["updated_at"] = _now()
        changed.append(row)

    _save(data)
    return {
        "ok": True,
        "items": items[-50:],
        "changed": changed[-50:],
        "live_deal_ids": list(live_deal_ids),
    }

def summarize_reconciliation():
    items = all_reconciliation_items()
    pending = [x for x in items if x.get("status") in ("SUBMITTED", "PENDING_BROKER")]
    confirmed = [x for x in items if x.get("status") == "CONFIRMED_CLOSED"]
    rejected = [x for x in items if x.get("status") == "REJECTED"]
    return {
        "pending_count": len(pending),
        "confirmed_count": len(confirmed),
        "rejected_count": len(rejected),
        "latest_items": items[-20:]
    }
