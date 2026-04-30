import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(BASE_DIR, "data", "ig_anomaly_registry.json")
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

def add_anomaly(kind, severity, details):
    data = _load()
    row = {
        "timestamp": _now(),
        "kind": kind,
        "severity": severity,
        "details": details or {}
    }
    data["items"] = (data.get("items") or [])[-999:] + [row]
    _save(data)
    return row

def list_anomalies(limit=50):
    return _load().get("items", [])[-int(limit):]
