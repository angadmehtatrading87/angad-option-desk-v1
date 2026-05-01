import json
import os
from datetime import datetime, timedelta, timezone

import yaml

from app.ig_api_governor import get_ig_cached_snapshot
from app.ig_session_intelligence import get_ig_session_state

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RISK_LIMITS_PATH = os.path.join(BASE_DIR, "config", "risk_limits.yaml")
IG_POLICY_PATH = os.path.join(BASE_DIR, "config", "ig_risk_policy.json")
BURST_STATE_PATH = os.path.join(BASE_DIR, "data", "execution_burst_guard.json")


def _load_yaml(path):
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _parse_ts(ts):
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _load_burst_state(path):
    state = _load_json(path)
    orders = state.get("orders", []) if isinstance(state, dict) else []
    return [x for x in orders if isinstance(x, str)]


def _save_burst_state(path, orders):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"orders": orders[-500:]}, f, indent=2)


def evaluate_execution_safety(channel, expected_order_count=1, ig_snapshot=None, now=None, burst_state_path=BURST_STATE_PATH):
    risk = _load_yaml(RISK_LIMITS_PATH)
    ig_policy = _load_json(IG_POLICY_PATH)

    reasons = []
    metadata = {"channel": channel}
    now = now or datetime.now(timezone.utc)

    if bool(risk.get("kill_switch", False)):
        reasons.append("kill_switch_active")

    account_mode = str(risk.get("account_mode") or "").strip().lower()
    if account_mode not in ("simulation", "demo", "live"):
        reasons.append("account_mode_not_explicit")
    if ig_policy.get("demo_only") is True and account_mode == "live":
        reasons.append("demo_only_policy_blocks_live_mode")

    session_state = get_ig_session_state() or {}
    session = str(session_state.get("session") or "").lower()
    market_open = bool(session_state.get("market_open", False))
    if not market_open or session in ("weekend_closed", "friday_close_window"):
        reasons.append("market_session_not_eligible")

    snap = ig_snapshot if ig_snapshot is not None else get_ig_cached_snapshot(force_refresh=False)
    if not snap or not snap.get("ok"):
        reasons.append("snapshot_unavailable")
    else:
        ts = _parse_ts(snap.get("timestamp"))
        max_age = int(ig_policy.get("safety_max_snapshot_age_seconds", 120) or 120)
        if not ts or (now - ts.astimezone(timezone.utc)) > timedelta(seconds=max_age):
            reasons.append("snapshot_stale")

        account = snap.get("account") or {}
        equity = _safe_float(account.get("equity"), 0.0)
        available = _safe_float(account.get("available"), 0.0)
        if equity <= 0:
            reasons.append("invalid_equity")
        else:
            liquidity_reserve = (available / equity) if equity > 0 else 0.0
            metadata["liquidity_reserve_ratio"] = round(liquidity_reserve, 4)
            if liquidity_reserve < 0.30:
                reasons.append("liquidity_reserve_below_30pct")

    orders = _load_burst_state(burst_state_path)
    window_seconds = int(ig_policy.get("safety_burst_window_seconds", 120) or 120)
    max_orders = int(ig_policy.get("safety_max_burst_orders", 3) or 3)
    window_start = now - timedelta(seconds=window_seconds)
    recent = []
    for item in orders:
        dt = _parse_ts(item)
        if dt and dt.astimezone(timezone.utc) >= window_start:
            recent.append(item)

    if len(recent) + int(expected_order_count or 0) > max_orders:
        reasons.append("max_burst_orders_exceeded")

    metadata.update({
        "burst_window_seconds": window_seconds,
        "max_burst_orders": max_orders,
        "current_window_orders": len(recent),
    })

    ok = len(reasons) == 0
    return {
        "ok": ok,
        "mode": "ALLOW" if ok else "REJECT",
        "reasons": reasons,
        "metadata": metadata,
    }


def record_execution_attempt(count=1, now=None, burst_state_path=BURST_STATE_PATH):
    now = now or datetime.now(timezone.utc)
    orders = _load_burst_state(burst_state_path)
    for _ in range(max(int(count or 0), 0)):
        orders.append(now.isoformat())
    _save_burst_state(burst_state_path, orders)
