"""
Cost cap meter — tracks daily usage of expensive services and trips a
kill-switch / Telegram alert when caps are breached.

Tracks five categories:
    - ig_api_calls          (every IGAdapter request)
    - ig_orders_submitted   (every order intent reaching the broker)
    - ig_position_opens     (only successful position opens)
    - llm_tokens            (input+output tokens across LLM calls)
    - llm_usd               (LLM dollar spend)

Counters reset at 00:00 Dubai time.

Public API:
    record(category: str, amount: int|float = 1, **meta) -> dict
        Increments the counter for `category`, returns the new state. Will
        also fire alerts and toggle kill-switches based on config/cost_cap.yaml.

    snapshot() -> dict
        Returns the full counter state for today. Cheap (file read).

    is_killed(switch: str) -> bool
        Cheap check used by callers (IGAdapter wrapper, agent_ops LLM caller)
        before they spend more.

    reset_today() -> None
        Manual reset for testing.

Storage: data/cost_cap_state.json (single file, rolled daily, atomic writes).
Config:  config/cost_cap.yaml.

Telegram alert dispatch:
    Uses app.telegram_alerts.send_telegram_message if available. Best-effort:
    we never let a Telegram failure block the meter.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "cost_cap.yaml")
STATE_PATH = os.path.join(BASE_DIR, "data", "cost_cap_state.json")
DXB = ZoneInfo("Asia/Dubai")

_lock = threading.Lock()


# --------------------------------------------------------------------------
# config / state I/O
# --------------------------------------------------------------------------

def _load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return _default_config()
    try:
        with open(CONFIG_PATH, "r") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        return _default_config()
    return cfg


def _default_config() -> dict:
    return {
        "caps": {
            "ig_api_calls_per_day": 5000,
            "llm_tokens_per_day": 200000,
            "llm_usd_per_day": 5.0,
            "ig_orders_submitted_per_day": 80,
            "ig_position_opens_per_day": 40,
        },
        "alerts": {"warn_at_pct": 80, "warn_again_at_pct": 95, "kill_at_pct": 100},
        "on_breach": {
            "ig_api_calls": {"alert_only": True},
            "llm_tokens": {"kill_llm_calls": True},
            "llm_usd": {"kill_llm_calls": True},
            "ig_orders_submitted": {"kill_trading": True},
            "ig_position_opens": {"kill_trading": True},
        },
    }


def _today_key() -> str:
    return datetime.now(DXB).strftime("%Y-%m-%d")


def _load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_PATH)


def _ensure_today(state: dict) -> dict:
    today = _today_key()
    day = state.get(today)
    if not day:
        day = {
            "date": today,
            "counters": {
                "ig_api_calls": 0,
                "ig_orders_submitted": 0,
                "ig_position_opens": 0,
                "llm_tokens": 0,
                "llm_usd": 0.0,
            },
            "alerts_sent": {},
            "kill_switches": {
                "llm_calls_killed": False,
                "trading_killed": False,
            },
        }
        state[today] = day
    return state


# --------------------------------------------------------------------------
# alert dispatch (best-effort)
# --------------------------------------------------------------------------

def _send_telegram(message: str) -> None:
    try:
        from app.telegram_alerts import send_telegram_message
        send_telegram_message(message)
    except Exception:
        # Never fail the meter because Telegram is down.
        pass


# --------------------------------------------------------------------------
# core API
# --------------------------------------------------------------------------

CAP_KEY_FOR_CATEGORY = {
    "ig_api_calls": "ig_api_calls_per_day",
    "ig_orders_submitted": "ig_orders_submitted_per_day",
    "ig_position_opens": "ig_position_opens_per_day",
    "llm_tokens": "llm_tokens_per_day",
    "llm_usd": "llm_usd_per_day",
}


def _evaluate_breach(category: str, used: float, cap: float, day: dict, cfg: dict) -> dict:
    """Decide what alert to send (if any) and which switches to flip."""
    out = {"alerts": [], "switches": []}
    if cap <= 0:
        return out
    pct = (used / cap) * 100.0
    thresholds = cfg.get("alerts", {})
    warn1 = float(thresholds.get("warn_at_pct", 80))
    warn2 = float(thresholds.get("warn_again_at_pct", 95))
    kill = float(thresholds.get("kill_at_pct", 100))

    sent = day["alerts_sent"].setdefault(category, [])
    on_breach = (cfg.get("on_breach") or {}).get(category, {})

    def _alert(level: str, msg: str):
        if level not in sent:
            out["alerts"].append({"level": level, "message": msg})
            sent.append(level)

    pretty_used = f"{used:,.2f}" if isinstance(used, float) else f"{used:,}"
    pretty_cap = f"{cap:,.2f}" if isinstance(cap, float) else f"{cap:,}"

    if pct >= kill:
        _alert("kill", f"⛔ {category} hit {pct:.0f}% of cap ({pretty_used}/{pretty_cap}). Triggering breach action.")
        if on_breach.get("kill_llm_calls"):
            day["kill_switches"]["llm_calls_killed"] = True
            out["switches"].append("llm_calls_killed")
        if on_breach.get("kill_trading"):
            day["kill_switches"]["trading_killed"] = True
            out["switches"].append("trading_killed")
    elif pct >= warn2:
        _alert("warn2", f"⚠️ {category} at {pct:.0f}% of cap ({pretty_used}/{pretty_cap}).")
    elif pct >= warn1:
        _alert("warn1", f"🟡 {category} at {pct:.0f}% of cap ({pretty_used}/{pretty_cap}).")
    return out


def record(category: str, amount: float = 1.0, **meta: Any) -> dict:
    """
    Record `amount` units against `category`. Returns the snapshot for today
    after the increment, including any alerts that fired.
    """
    if category not in CAP_KEY_FOR_CATEGORY:
        # Unknown category — refuse silently rather than poisoning state.
        return {"ok": False, "reason": f"unknown_category:{category}"}

    cfg = _load_config()
    cap_key = CAP_KEY_FOR_CATEGORY[category]
    cap = float((cfg.get("caps") or {}).get(cap_key, 0))

    with _lock:
        state = _load_state()
        state = _ensure_today(state)
        day = state[_today_key()]
        day["counters"][category] = float(day["counters"].get(category, 0)) + float(amount)
        used = day["counters"][category]
        breach = _evaluate_breach(category, used, cap, day, cfg)
        _save_state(state)

    for alert in breach["alerts"]:
        _send_telegram(alert["message"])

    return {
        "ok": True,
        "category": category,
        "used": used,
        "cap": cap,
        "pct_of_cap": (used / cap * 100.0) if cap > 0 else 0.0,
        "alerts_fired": breach["alerts"],
        "switches_flipped": breach["switches"],
    }


def snapshot() -> dict:
    cfg = _load_config()
    state = _load_state()
    state = _ensure_today(state)
    day = state[_today_key()]
    counters = day.get("counters", {})
    caps = cfg.get("caps", {})

    rows = []
    for cat, cap_key in CAP_KEY_FOR_CATEGORY.items():
        used = counters.get(cat, 0)
        cap = caps.get(cap_key, 0)
        pct = (float(used) / float(cap) * 100.0) if cap else 0.0
        rows.append({"category": cat, "used": used, "cap": cap, "pct": round(pct, 2)})

    return {
        "date": day["date"],
        "rows": rows,
        "kill_switches": day.get("kill_switches", {}),
        "alerts_sent": day.get("alerts_sent", {}),
    }


def is_killed(switch: str) -> bool:
    """`switch` is one of: 'llm_calls_killed', 'trading_killed'."""
    state = _load_state()
    state = _ensure_today(state)
    day = state[_today_key()]
    return bool(day.get("kill_switches", {}).get(switch, False))


def reset_today() -> None:
    with _lock:
        state = _load_state()
        state.pop(_today_key(), None)
        _save_state(state)
