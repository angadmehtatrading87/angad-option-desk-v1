import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ig_adapter import IGAdapter
from app.virtual_portfolio import virtual_account_snapshot

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(BASE_DIR, "data", "lane_capital_state.json")
DXB = ZoneInfo("Asia/Dubai")

DEFAULTS = {
    "ig_enabled": True,
    "tasty_enabled": False,
    "ig_max_usage_pct": 80.0,
    "tasty_starting_capital": 1000000.0,
    "tasty_max_usage_pct": 80.0
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
        "account_id": body.get("currentAccountId")
    }

def tasty_lane_snapshot():
    st = ensure_lane_state()
    cfg = st["config"]
    snap = virtual_account_snapshot()

    seeded_capital = _safe_float(cfg.get("tasty_starting_capital", 1000000.0))
    cash = _safe_float(snap.get("cash_balance"), seeded_capital)
    realized = _safe_float(snap.get("realized_pnl"))
    unrealized = _safe_float(snap.get("unrealized_pnl"))
    total_equity = _safe_float(snap.get("total_equity"), cash + unrealized)

    if total_equity <= 0:
        total_equity = seeded_capital
        cash = seeded_capital
        realized = 0.0
        unrealized = 0.0

    open_positions = snap.get("open_positions", []) or []
    deployed = 0.0
    for p in open_positions:
        deployed += _safe_float(p.get("reserved_capital"))

    usage_pct = (deployed / total_equity * 100.0) if total_equity > 0 else 0.0

    return {
        "ok": True,
        "starting_capital": round(seeded_capital, 2),
        "cash_balance": round(cash, 2),
        "realized_pnl": round(realized, 2),
        "unrealized_pnl": round(unrealized, 2),
        "equity": round(total_equity, 2),
        "deployed": round(deployed, 2),
        "usage_pct": round(usage_pct, 2),
        "open_positions": len(open_positions)
    }

def lane_entry_allowed(lane: str):
    st = ensure_lane_state()
    cfg = st["config"]

    if lane == "ig":
        if not cfg.get("ig_enabled", True):
            return False, "ig_lane_disabled"
        snap = ig_lane_snapshot()
        if not snap.get("ok"):
            return False, "ig_lane_snapshot_failed"
        if snap["usage_pct"] >= _safe_float(cfg.get("ig_max_usage_pct", 80.0)):
            return False, "ig_lane_cap_reached"
        return True, "ok"

    if lane == "tasty":
        if not cfg.get("tasty_enabled", True):
            return False, "tasty_lane_disabled"
        snap = tasty_lane_snapshot()
        if snap["usage_pct"] >= _safe_float(cfg.get("tasty_max_usage_pct", 80.0)):
            return False, "tasty_lane_cap_reached"
        return True, "ok"

    return False, "unknown_lane"

def lane_capital_state():
    st = ensure_lane_state()
    return {
        "updated_at": _now(),
        "config": st["config"],
        "ig": ig_lane_snapshot(),
        "tasty": tasty_lane_snapshot()
    }
