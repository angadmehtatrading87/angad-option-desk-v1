from app.lane_capital_controller import lane_entry_allowed
from app.daily_objective_controller import combined_entry_allowed
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from app.market_prep_brain import load_market_prep_state, STATE_PATH
from app.virtual_portfolio import virtual_account_snapshot, list_open_virtual_positions
from app.spread_builder import propose_spread_candidates
from app.virtual_execution import open_virtual_trade

DXB = ZoneInfo("Asia/Dubai")

def _now():
    return datetime.now(DXB).isoformat()

def current_open_symbols():
    return [str(p.get("symbol") or "").upper() for p in list_open_virtual_positions()]

def current_open_strategies():
    return [str(p.get("strategy") or "").lower() for p in list_open_virtual_positions()]

def deployed_capital_pct(snapshot):
    start = float(snapshot.get("starting_capital", 0) or 0)
    cash = float(snapshot.get("cash_balance", 0) or 0)
    if start <= 0:
        return 0.0
    return round(((start - cash) / start) * 100, 2)

def can_enter_from_plan():
    state = load_market_prep_state()
    plan = state.get("session_plan", {})
    snap = virtual_account_snapshot()
    reasons = []

    if plan.get("owner_approval_required", False):
        reasons.append("owner_approval_required_enabled")
    if not plan.get("autonomous_entries", True):
        reasons.append("autonomous_entries_disabled")
    if plan.get("day_mode", "NO_TRADE") == "NO_TRADE":
        reasons.append("day_mode_no_trade")
    if len(list_open_virtual_positions()) >= int(plan.get("max_concurrent_trades", 999)):
        reasons.append("max_concurrent_trades_reached")
    if deployed_capital_pct(snap) >= float(plan.get("max_deployed_capital_pct", 70)):
        reasons.append("max_deployed_capital_reached")

    return {"ok": len(reasons) == 0, "reasons": reasons, "plan": plan, "snapshot": snap}

def _candidate_matches_strategy(candidate, strategy_name):
    setup = str(candidate.get("setup_name") or "").lower()
    mapping = {
        "call_debit_spread": ["call_debit_spread"],
        "put_debit_spread": ["put_debit_spread"],
        "put_credit_spread": ["put_credit_spread"],
    }
    allowed = mapping.get(str(strategy_name or "").lower(), [])
    return setup in allowed

def _top_execution_ready_choice(strategy_row):
    choices = strategy_row.get("execution_ready_choices", [])
    if not choices:
        return None
    return choices[0]

def build_candidate_pool_from_universal_map():
    state = load_market_prep_state()
    plan = state.get("session_plan", {})
    universal_map = plan.get("universal_strategy_map", [])
    pool = []

    for row in universal_map:
        symbol = (row.get("symbol") or "").upper()
        if not symbol:
            continue

        chosen = _top_execution_ready_choice(row)
        if not chosen:
            continue

        chosen_strategy = str(chosen.get("strategy_name") or "").lower()
        created = propose_spread_candidates(symbol)

        for c in created:
            if c.get("grade") != "A":
                continue
            if c.get("agent_view") != "APPROVE":
                continue
            if not _candidate_matches_strategy(c, chosen_strategy):
                continue

            c["plan_symbol"] = symbol
            c["universal_strategy"] = chosen_strategy
            c["universal_family"] = chosen.get("family")
            c["universal_score"] = chosen.get("score", 0)
            c["selection_mode"] = "universal_execution"
            pool.append(c)

    pool = sorted(
        pool,
        key=lambda x: (
            -(x.get("universal_score", 0)),
            -(x.get("confidence", 0)),
            x.get("max_risk", 9999999)
        )
    )
    return pool

def select_entries():
    gate = can_enter_from_plan()
    if not gate["ok"]:
        return {"ok": False, "reason": gate["reasons"], "selected": [], "debug_pool_size": 0}

    plan = gate["plan"]
    max_entries = int(plan.get("max_new_entries", 999))
    pool = build_candidate_pool_from_universal_map()

    selected = []
    open_syms = set(current_open_symbols())
    open_strats = set(current_open_strategies())

    min_risk_allowed = float(plan.get("min_risk_per_trade_usd", 50000) or 50000)
    max_risk_allowed = float(plan.get("max_risk_per_trade_usd", 100000) or 100000)

    for c in pool:
        sym = (c.get("symbol") or "").upper()
        strat = str(c.get("strategy") or "").lower()
        unit_risk = float(c.get("max_risk", 0) or 0)

        if sym in open_syms:
            continue
        if strat in open_strats:
            continue
        if unit_risk <= 0:
            continue

        qty = int(max_risk_allowed // unit_risk)
        if qty < 1:
            continue

        total_risk = round(unit_risk * qty, 2)
        if total_risk < min_risk_allowed:
            continue

        c["quantity"] = qty
        c["scaled_max_risk"] = total_risk
        selected.append(c)

        open_syms.add(sym)
        open_strats.add(strat)

        if len(selected) >= max_entries:
            break

    if not selected and pool:
        for c in pool[:3]:
            conf = float(c.get("confidence", 0) or 0)
            q = float(c.get("quality_score", 0) or 0)
            if conf >= 65 and q >= 70:
                c = dict(c)
                c["agent_view"] = "EXPLORE"
                c["selection_mode"] = "exploration_fallback"
                c["quantity"] = min(int(c.get("quantity", 1) or 1), 2)
                c["quantity"] = min(int(c.get("quantity", 1) or 1), 2)
                selected = [c]
                break

    for c in selected:
        try:
            c["quantity"] = min(max(int(c.get("quantity", 1) or 1), 1), 2)
            c["scaled_max_risk"] = min(float(c.get("scaled_max_risk", 0) or 0), 1500.0)
            c["max_risk"] = min(float(c.get("max_risk", 0) or 0), 1500.0)
        except Exception:
            pass

    return {
        "ok": True,
        "reason": [],
        "selected": selected,
        "debug_pool_size": len(pool)
    }

def run_autonomous_entries():
    allowed_combined, reason_combined = combined_entry_allowed()
    if not allowed_combined and reason_combined not in ("combined_capital_usage_cap_reached", "combined_daily_target_hit_soft_lock"):
        return {
            "ok": False,
            "entered": [],
            "reason": [reason_combined],
            "debug_pool_size": 0
        }

    allowed_tasty_lane, reason_tasty_lane = lane_entry_allowed("tasty")
    if not allowed_tasty_lane:
        return {
            "ok": False,
            "entered": [],
            "reason": [reason_tasty_lane],
            "debug_pool_size": 0
        }

    state = load_market_prep_state()
    results = []
    decision = select_entries()

    state.setdefault("execution_brain", {})
    state["execution_brain"]["last_run_dxb"] = _now()
    state["execution_brain"]["selection_result"] = decision

    if not decision["ok"]:
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
        return {"ok": False, "entered": [], "reason": decision["reason"], "debug_pool_size": 0}

    for c in decision["selected"]:
        trade_id = c["trade_id"]
        qty = int(c.get("quantity", 1))
        try:
            result = open_virtual_trade(trade_id, quantity=qty)
            results.append({
                "trade_id": trade_id,
                "symbol": c.get("symbol"),
                "status": result.get("status"),
                "quantity": qty,
                "max_risk": c.get("scaled_max_risk"),
                "confidence": c.get("confidence"),
                "selection_mode": c.get("selection_mode"),
                "universal_strategy": c.get("universal_strategy"),
                "universal_family": c.get("universal_family"),
            })
        except Exception as e:
            results.append({
                "trade_id": trade_id,
                "symbol": c.get("symbol"),
                "status": "ENTRY_ERROR",
                "quantity": qty,
                "error": str(e),
                "selection_mode": c.get("selection_mode"),
                "universal_strategy": c.get("universal_strategy"),
                "universal_family": c.get("universal_family"),
            })

    state["execution_brain"]["entry_results"] = results
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    return {
        "ok": True,
        "entered": results,
        "reason": [],
        "debug_pool_size": decision.get("debug_pool_size", 0)
    }
