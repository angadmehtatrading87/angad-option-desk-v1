"""
Capital lane controller — IG-only.

Historically this controller managed two separate capital lanes (IG live and
Tastytrade virtual). Tastytrade has been removed; this module now exposes a
single IG lane while keeping the public function names (`lane_entry_allowed`,
`lane_capital_state`) stable so callers don't have to change.
"""

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ig_adapter import IGAdapter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(BASE_DIR, "data", "lane_capital_state.json")
DXB = ZoneInfo("Asia/Dubai")

DEFAULTS = {
    "ig_enabled": True,
    "ig_max_usage_pct": 80.0,
}


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _now():
    return datetime.now(DXB).isoformat()


def _load():
    if not os.path.exists(STATE_PATH):
        return {"config": DEFAULTS, "updated_at": None}
    with open(STATE_PATH, "r") as f:
        return json.load(f)


def _save(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def ensure_lane_state():
    st = _load()
    changed = False
    if "config" not in st:
        st["config"] = DEFAULTS
        changed = True
    else:
        for k, v in DEFAULTS.items():
            if k not in st["config"]:
                st["config"][k] = v
                changed = True
        # Drop stale tasty_* keys if a previous state file persisted them.
        for stale_key in list(st["config"].keys()):
            if stale_key.startswith("tasty_"):
                st["config"].pop(stale_key, None)
                changed = True
    st["updated_at"] = _now()
    if changed:
        _save(st)
    return st


def ig_lane_snapshot():
    ig = IGAdapter()
    login = ig.login()
    if not login.get("ok"):
        return {"ok": False, "equity": 0.0, "available": 0.0, "usage_pct": 0.0}

    body = login.get("body") or {}
    info = body.get("accountInfo", {}) or {}
    balance = _safe_float(info.get("balance"))
    pnl = _safe_float(info.get("profitLoss"))
    available = _safe_float(info.get("available"))
    equity = balance + pnl
    deployed = max(0.0, equity - available)
    usage_pct = (deployed / equity * 100.0) if equity > 0 else 0.0

    return {
        "ok": True,
        "equity": round(equity, 2),
        "available": round(available, 2),
        "deployed": round(deployed, 2),
        "usage_pct": round(usage_pct, 2),
        "account_id": body.get("currentAccountId"),
    }


def lane_entry_allowed(lane: str = "ig"):
    """
    Returns (allowed: bool, reason: str). The `lane` argument is kept for
    backward compatibility — only "ig" is supported. Anything else is rejected
    with `unknown_lane`.
    """
    st = ensure_lane_state()
    cfg = st["config"]

    if lane != "ig":
        return False, "unknown_lane"

    if not cfg.get("ig_enabled", True):
        return False, "ig_lane_disabled"
    snap = ig_lane_snapshot()
    if not snap.get("ok"):
        return False, "ig_lane_snapshot_failed"
    if snap["usage_pct"] >= _safe_float(cfg.get("ig_max_usage_pct", 80.0)):
        return False, "ig_lane_cap_reached"
    return True, "ok"


def lane_capital_state():
    st = ensure_lane_state()
    return {
        "updated_at": _now(),
        "config": st["config"],
        "ig": ig_lane_snapshot(),
    }
