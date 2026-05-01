import hashlib
import json
import os
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(BASE_DIR, "data", "execution_two_phase_state.json")


def _parse_ts(ts):
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _load_state(path=STATE_PATH):
    try:
        with open(path, "r") as f:
            state = json.load(f) or {}
    except Exception:
        state = {}

    intents = state.get("intents") if isinstance(state, dict) else []
    if not isinstance(intents, list):
        intents = []
    return intents


def _save_state(intents, path=STATE_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"intents": intents[-2000:]}, f, indent=2)


def _intent_key(epic, direction, size):
    payload = f"{str(epic or '').strip()}|{str(direction or '').upper()}|{_safe_float(size):.4f}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def prepare_intent(epic, direction, size, now=None, hold_seconds=90, state_path=STATE_PATH):
    now = now or datetime.now(timezone.utc)
    key = _intent_key(epic, direction, size)

    intents = _load_state(state_path)
    active_cutoff = now - timedelta(seconds=max(int(hold_seconds or 90), 10))

    retained = []
    active_for_key = []
    for row in intents:
        ts = _parse_ts(row.get("prepared_at"))
        status = str(row.get("status") or "").upper()

        if status in ("COMMITTED", "ABORTED"):
            retained.append(row)
            continue

        if not ts or ts.astimezone(timezone.utc) < active_cutoff:
            continue

        retained.append(row)
        if row.get("intent_key") == key and status == "PREPARED":
            active_for_key.append(row)

    if active_for_key:
        _save_state(retained, state_path)
        return {
            "ok": False,
            "intent_key": key,
            "reason": "intent_already_prepared",
            "metadata": {"active_prepared_count": len(active_for_key), "hold_seconds": int(hold_seconds or 90)},
        }

    row = {
        "intent_key": key,
        "epic": epic,
        "direction": str(direction or "").upper(),
        "size": round(_safe_float(size), 4),
        "prepared_at": now.isoformat(),
        "status": "PREPARED",
        "committed_at": None,
        "aborted_at": None,
        "deal_reference": None,
        "deal_id": None,
        "note": "",
    }
    retained.append(row)
    _save_state(retained, state_path)
    return {"ok": True, "intent_key": key, "reason": "prepared"}


def finalize_intent(intent_key, status, now=None, deal_reference=None, deal_id=None, note="", state_path=STATE_PATH):
    now = now or datetime.now(timezone.utc)
    normalized = str(status or "").upper()
    if normalized not in ("COMMITTED", "ABORTED"):
        return {"ok": False, "reason": "invalid_finalize_status"}

    intents = _load_state(state_path)
    updated = False
    for row in intents:
        if row.get("intent_key") != intent_key:
            continue
        row["status"] = normalized
        row["deal_reference"] = deal_reference
        row["deal_id"] = deal_id
        row["note"] = note
        if normalized == "COMMITTED":
            row["committed_at"] = now.isoformat()
        else:
            row["aborted_at"] = now.isoformat()
        updated = True

    if not updated:
        return {"ok": False, "reason": "intent_not_found"}

    _save_state(intents, state_path)
    return {"ok": True, "reason": normalized.lower(), "intent_key": intent_key}
