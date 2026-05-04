"""
Daily objective controller — IG-only.

Tracks daily P&L target, hard-loss limit, and capital-usage cap against the
IG account. The legacy multi-broker (IG + Tastytrade) version of this module
exposed a "combined" view; the public shape is preserved for backward
compatibility — `live.combined` now mirrors `live.ig`.
"""

import json
import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")
STATE_PATH = os.path.join(BASE_DIR, "data", "daily_objective_state.json")
DXB = ZoneInfo("Asia/Dubai")

DEFAULTS = {
    "combined_daily_target_pct": 1.0,
    "combined_daily_hard_loss_pct": 1.0,
    "combined_daily_soft_lock_after_target": False,
    "combined_max_capital_usage_pct": 80.0,
}


def _today_key():
    return datetime.now(DXB).strftime("%Y-%m-%d")


def _now():
    return datetime.now(DXB).isoformat()


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _load_state():
    if not os.path.exists(STATE_PATH):
        return {}
    with open(STATE_PATH, "r") as f:
        return json.load(f)


def _save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def _ig_snapshot():
    try:
        from app.ig_api_governor import get_ig_cached_snapshot
        snap = get_ig_cached_snapshot(force_refresh=False) or {}
        acct = (snap.get("account") or {})
        return {
            "equity": _safe_float(acct.get("equity")),
            "available": _safe_float(acct.get("available")),
            "open_pnl": _safe_float(acct.get("open_pnl")),
            "balance": _safe_float(acct.get("balance")),
            "account_id": acct.get("account_id"),
        }
    except Exception:
        return {
            "equity": 0.0,
            "available": 0.0,
            "open_pnl": 0.0,
            "balance": 0.0,
            "account_id": None,
        }


def _ensure_today_state():
    state = _load_state()
    today = _today_key()
    if state.get("date") != today:
        ig = _ig_snapshot()
        ig_start = ig.get("equity", 0.0)

        state = {
            "date": today,
            "created_at": _now(),
            "updated_at": _now(),
            "config": DEFAULTS,
            "start": {
                "ig_equity": ig_start,
                "combined_equity": ig_start,  # back-compat: combined == ig
            },
            "withdrawal_pool": {
                "target_pct": DEFAULTS["combined_daily_target_pct"],
                "target_amount": round(ig_start * DEFAULTS["combined_daily_target_pct"] / 100.0, 2),
                "locked_amount": 0.0,
            },
            "status": {
                "target_hit": False,
                "soft_locked": False,
                "hard_stopped": False,
            },
        }
        _save_state(state)
    return state


def compute_daily_objective_state():
    today = _today_key()
    full_state = _load_state() or {}
    state = full_state.get(today, {}) or {}

    if not state:
        _ensure_today_state()
        full_state = _load_state() or {}
        state = full_state.get(today, {}) or {}

    start = state.get("start", {}) or {}
    cfg = state.get("config", {}) or {}
    withdrawal_pool = state.get("withdrawal_pool", {}) or {}

    ig = _ig_snapshot()

    ig_now = _safe_float(ig.get("equity"))
    ig_start = _safe_float(start.get("ig_equity"))
    combined_start = _safe_float(start.get("combined_equity")) or ig_start

    ig_day_pnl = round(ig_now - ig_start, 2)
    combined_day_pnl = ig_day_pnl  # IG is the only lane

    target_amount = round(combined_start * _safe_float(cfg.get("combined_daily_target_pct", 1.0)) / 100.0, 2)
    hard_loss_amount = round(combined_start * _safe_float(cfg.get("combined_daily_hard_loss_pct", 1.0)) / 100.0, 2)

    target_hit = combined_day_pnl >= target_amount if target_amount > 0 else False
    hard_stopped = combined_day_pnl <= (-hard_loss_amount) if hard_loss_amount > 0 else False
    soft_locked = bool(target_hit and cfg.get("combined_daily_soft_lock_after_target", True))

    ig_available = _safe_float(ig.get("available"))
    ig_deployed = max(0.0, ig_now - ig_available) if ig_now > ig_available else 0.0
    combined_deployed_est = max(0.0, ig_deployed)

    capital_usage_cap_amount = round(combined_start * _safe_float(cfg.get("combined_max_capital_usage_pct", 80.0)) / 100.0, 2)
    capital_usage_pct = round((combined_deployed_est / combined_start) * 100.0, 2) if combined_start > 0 else 0.0
    usage_blocked = combined_deployed_est >= capital_usage_cap_amount if capital_usage_cap_amount > 0 else False

    target_progress_pct = round((combined_day_pnl / target_amount) * 100.0, 2) if target_amount > 0 else 0.0

    state["status"] = {
        "target_hit": bool(target_hit),
        "soft_locked": bool(soft_locked),
        "hard_stopped": bool(hard_stopped),
    }
    full_state[today] = state
    _save_state(full_state)

    return {
        "date": today,
        "created_at": state.get("created_at"),
        "updated_at": state.get("updated_at"),
        "config": cfg,
        "start": start,
        "withdrawal_pool": withdrawal_pool,
        "status": state.get("status", {}),
        "live": {
            "ig": {
                "equity": round(ig_now, 2),
                "day_pnl": ig_day_pnl,
                "available": round(ig_available, 2),
                "open_pnl": round(_safe_float(ig.get("open_pnl")), 2),
                "account_id": ig.get("account_id"),
            },
            "combined": {
                "start_equity": round(combined_start, 2),
                "current_equity": round(ig_now, 2),
                "day_pnl": combined_day_pnl,
                "target_amount": round(target_amount, 2),
                "hard_loss_amount": round(hard_loss_amount, 2),
                "target_progress_pct": round(target_progress_pct, 2),
                "capital_usage_est": round(combined_deployed_est, 2),
                "capital_usage_pct": round(capital_usage_pct, 2),
                "capital_usage_cap_amount": round(capital_usage_cap_amount, 2),
                "usage_blocked": bool(usage_blocked),
            },
        },
    }


def combined_entry_allowed():
    state = compute_daily_objective_state()
    status = state.get("status", {})
    combined = ((state.get("live") or {}).get("combined") or {})

    if status.get("hard_stopped"):
        return False, "combined_daily_hard_stop_hit"
    if status.get("soft_locked"):
        return False, "combined_daily_target_hit_soft_lock_bypassed"
    if combined.get("usage_blocked"):
        return False, "combined_capital_usage_cap_reached"
    return True, "ok"
