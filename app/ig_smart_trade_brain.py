import json
import os
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.ig_adapter import IGAdapter
from app.ig_decision_engine import build_ig_decisions
from app.ig_session_intelligence import get_ig_session_state
from app.ig_weekend_carry_controller import get_weekend_carry_policy
from app.ig_position_management import rank_managed_positions, choose_management_actions
from app.ig_api_governor import get_ig_cached_snapshot
from app.ig_regime_intelligence import classify_market_regime, get_entry_expression
from app.ig_asia_open_playbook import evaluate_asia_open_playbook

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")
STATE_PATH = os.path.join(BASE_DIR, "data", "ig_smart_trade_state.json")
DXB = ZoneInfo("Asia/Dubai")

REENTRY_COOLDOWN_MINUTES = 8
PROFIT_REDUCED_RISK_THRESHOLD_USD = 25.0
PROFIT_HARVEST_PCT = 1.0

def _now():
    return datetime.now(DXB)

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def _load_state():
    if not os.path.exists(STATE_PATH):
        return {"last_exit_by_epic": {}, "reduced_risk_mode": False, "profit_harvest_mode": False}
    with open(STATE_PATH, "r") as f:
        return json.load(f)

def _save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _recent_realized_profit():
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT raw_response
        FROM ig_trade_log
        ORDER BY id DESC
        LIMIT 50
    """)
    rows = cur.fetchall()
    conn.close()
    realized = 0.0
    for r in rows:
        raw = r["raw_response"]
        if not raw:
            continue
        try:
            body = json.loads(raw)
        except Exception:
            continue
        if isinstance(body, dict):
            pnl = body.get("profit")
            if pnl is not None:
                realized += _safe_float(pnl)
    return round(realized, 2)

def _ig_account_snapshot():
    snap = get_ig_cached_snapshot()
    acct = snap.get("account", {}) or {}
    if not acct.get("ok"):
        return {"ok": False, "balance": 0.0, "open_pnl": 0.0, "equity": 0.0, "harvest_mode": False}

    balance = _safe_float(acct.get("balance"))
    open_pnl = _safe_float(acct.get("open_pnl"))
    equity = _safe_float(acct.get("equity"))
    harvest_trigger = balance * (PROFIT_HARVEST_PCT / 100.0) if balance > 0 else 0.0
    harvest_mode = open_pnl >= harvest_trigger and harvest_trigger > 0

    return {
        "ok": True,
        "balance": round(balance, 2),
        "open_pnl": round(open_pnl, 2),
        "equity": round(equity, 2),
        "harvest_trigger": round(harvest_trigger, 2),
        "harvest_mode": bool(harvest_mode),
    }

def get_live_positions():
    snap = get_ig_cached_snapshot()
    pos = snap.get("positions", {}) or {}
    rows = pos.get("positions", []) or []
    if not pos.get("ok"):
        return {"ok": False, "positions": []}

    out = []
    for row in rows:
        bid = _safe_float(row.get("bid"))
        offer = _safe_float(row.get("offer"))
        entry = _safe_float(row.get("level"))
        direction = str(row.get("direction") or "").upper()

        if direction == "BUY":
            mark = bid
            pnl_points = mark - entry
        else:
            mark = offer
            pnl_points = entry - mark

        out.append({
            "epic": row.get("epic"),
            "name": row.get("name"),
            "deal_id": row.get("deal_id"),
            "deal_reference": row.get("deal_reference"),
            "direction": direction,
            "size": _safe_float(row.get("size")),
            "entry_level": entry,
            "mark_level": mark,
            "stop_level": row.get("stop_level"),
            "limit_level": row.get("limit_level"),
            "percentage_change": _safe_float(row.get("percentage_change")),
            "market_status": row.get("market_status"),
            "pnl_points": round(pnl_points, 4),
        })
    return {"ok": True, "positions": out}

def _signal_map():
    data = build_ig_decisions()
    mp = {}
    for d in data.get("decisions", []):
        mp[d.get("epic")] = d
    return mp

def evaluate_live_positions():
    state = _load_state()
    signals = _signal_map()
    live = get_live_positions()
    positions = live.get("positions", [])
    acct = _ig_account_snapshot()
    harvest_mode = bool(acct.get("harvest_mode", False))
    session_state = get_ig_session_state()
    carry_policy = get_weekend_carry_policy()

    managed = []
    for p in positions:
        sig = signals.get(p["epic"], {})
        action = sig.get("action", "NO_TRADE")
        conf = _safe_float(sig.get("confidence"))
        reason = sig.get("reason", "No active signal")
        pct = _safe_float(p.get("percentage_change"))
        pnl_pts = _safe_float(p.get("pnl_points"))
        direction = p["direction"]
        size = _safe_float(p["size"])

        desired = "HOLD"
        why = "Default hold"
        partial_size = max(1.0, round(size / 2.0, 4))

        aligned = (
            (action == "WATCH_LONG" and direction == "BUY") or
            (action == "WATCH_SHORT" and direction == "SELL")
        )
        conflict = (
            (action == "WATCH_LONG" and direction == "SELL") or
            (action == "WATCH_SHORT" and direction == "BUY")
        )

        if carry_policy.get("flatten_all"):
            desired = "CLOSE_NOW"
            why = "Weekend/close controller: flatten non-essential exposure."
        elif carry_policy.get("reduce_only") and pnl_pts > 0:
            desired = "TAKE_PROFIT"
            why = "Weekend/session reduction controller: reduce profitable exposure."
        elif conflict:
            desired = "CLOSE_NOW"
            why = "Position conflicts with current signal."
        elif aligned:
            if harvest_mode:
                if pnl_pts > 8 and conf >= 78 and abs(pct) >= 0.12:
                    desired = "TAKE_PARTIAL"
                    why = "Profit-harvest mode: trim winner and keep runner."
                elif pnl_pts > 0:
                    desired = "TAKE_PROFIT"
                    why = "Profit-harvest mode: crystallize gain."
                elif pnl_pts < -4:
                    desired = "CLOSE_NOW"
                    why = "Profit-harvest mode: cut weak laggard."
                else:
                    desired = "HOLD"
                    why = "Profit-harvest mode: hold only if runner not proven yet."
            else:
                if pnl_pts > 8 and conf >= 75 and abs(pct) >= 0.12:
                    desired = "HOLD"
                    why = "Strong trend and profit still alive."
                elif pnl_pts > 5 and conf >= 60 and abs(pct) >= 0.08:
                    desired = "TAKE_PARTIAL"
                    why = "Good profit booked while keeping runner alive."
                elif pnl_pts > 0 and conf < 58:
                    desired = "TAKE_PROFIT"
                    why = "Profit available but signal confidence is fading."
                elif pnl_pts < -5 and conf < 55:
                    desired = "CLOSE_NOW"
                    why = "Losing trade with weak signal."
                else:
                    desired = "HOLD"
                    why = "Signal still aligned."
        else:
            if pnl_pts > 0:
                desired = "TAKE_PROFIT"
                why = "No fresh aligned signal; lock profit."
            else:
                desired = "CLOSE_NOW"
                why = "No aligned signal and trade not working."

        managed.append({
            **p,
            "signal_action": action,
            "signal_confidence": conf,
            "signal_reason": reason,
            "agent_action": desired,
            "agent_reason": why,
            "partial_size": min(size, partial_size)
        })

    regime_state = classify_market_regime(
        positions=[{
            "epic": p.get("epic"),
            "percentage_change": p.get("percentage_change"),
            "market_status": p.get("market_status")
        } for p in managed],
        session_state=session_state
    )
    entry_expression = get_entry_expression(regime_state, session_state=session_state)
    asia_playbook = evaluate_asia_open_playbook()

    for p in managed:
        p["regime"] = regime_state.get("regime")
        p["regime_conviction"] = regime_state.get("conviction_score")
        p["entry_style"] = entry_expression.get("entry_style")
        p["size_multiplier_hint"] = entry_expression.get("size_multiplier")
        p["probe_only"] = entry_expression.get("probe_only") or asia_playbook.get("probe_allowed", False)
        p["asia_action_bias"] = asia_playbook.get("action_bias")
        p["asia_size_multiplier"] = asia_playbook.get("size_multiplier")

    ranked_managed = rank_managed_positions(managed, session_state=session_state, carry_policy=carry_policy)
    final_managed = choose_management_actions(ranked_managed, session_state=session_state, carry_policy=carry_policy)

    reduced_risk_mode = _recent_realized_profit() >= PROFIT_REDUCED_RISK_THRESHOLD_USD
    state["reduced_risk_mode"] = bool(reduced_risk_mode)
    state["profit_harvest_mode"] = bool(harvest_mode)
    _save_state(state)

    return {
        "ok": True,
        "managed_positions": final_managed,
        "reduced_risk_mode": reduced_risk_mode,
        "profit_harvest_mode": harvest_mode,
        "account_snapshot": acct,
        "session_state": session_state,
        "carry_policy": carry_policy,
        "regime_state": regime_state,
        "entry_expression": entry_expression,
        "asia_playbook": asia_playbook
    }

def mark_exit_for_reentry(epic):
    state = _load_state()
    state.setdefault("last_exit_by_epic", {})[epic] = _now().isoformat()
    _save_state(state)

def reentry_allowed(epic):
    state = _load_state()
    last = (state.get("last_exit_by_epic") or {}).get(epic)
    if not last:
        return True, "ok"
    try:
        last_dt = datetime.fromisoformat(last)
    except Exception:
        return True, "ok"
    if _now() < last_dt + timedelta(minutes=REENTRY_COOLDOWN_MINUTES):
        return False, "reentry_cooldown_active"
    return True, "ok"

def size_multiplier():
    state = _load_state()
    return 0.5 if state.get("reduced_risk_mode") else 1.0
