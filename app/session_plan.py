import json
from datetime import datetime
from zoneinfo import ZoneInfo

from app.market_prep_brain import load_market_prep_state, STATE_PATH
from app.agent_policy import load_agent_policy
from app.strategy_selector import choose_strategy_families

DXB = ZoneInfo("Asia/Dubai")

def _now():
    return datetime.now(DXB).isoformat()

def build_session_plan():
    state = load_market_prep_state()
    policy = load_agent_policy()

    regime = state.get("regime_view", {}).get("regime", "MIXED")
    style = state.get("regime_view", {}).get("style", "selective")
    confidence = state.get("regime_view", {}).get("confidence", 50)
    top_focus = state.get("opportunity_ranking", {}).get("top_trade_focus", [])
    focus_symbols = [x.get("symbol") for x in top_focus if x.get("symbol")]

    risk_cfg = policy.get("risk", {})
    exec_cfg = policy.get("execution", {})
    regime_cfg = policy.get("regime", {})

    no_trade = False
    reasons = []

    if regime == "EVENT_RISK" and not regime_cfg.get("allow_trade_in_event_risk", False):
        no_trade = True
        reasons.append("event_risk_block")

    if regime == "NO_TRADE" and not regime_cfg.get("allow_trade_in_no_trade_regime", False):
        no_trade = True
        reasons.append("no_trade_regime_block")

    if not top_focus:
        no_trade = True
        reasons.append("no_ranked_opportunities")

    if confidence < 45:
        reasons.append("low_regime_confidence")

    if no_trade:
        day_mode = "NO_TRADE"
    elif confidence >= 65 and len(top_focus) >= 2:
        day_mode = "ACTIVE_TRADE"
    else:
        day_mode = "SELECTIVE_TRADE"

    preferred_structures = state.get("regime_view", {}).get("preferred_structures", [])
    forbidden_structures = state.get("regime_view", {}).get("forbidden_structures", [])

    max_new_entries = min(
        int(exec_cfg.get("max_new_entries_per_session", 999)),
        len(top_focus) if top_focus else 0
    )

    if day_mode == "NO_TRADE":
        max_new_entries = 0

    universal_strategy_map = choose_strategy_families(top_focus, regime)

    plan = {
        "generated_at_dxb": _now(),
        "day_mode": day_mode,
        "regime": regime,
        "style": style,
        "confidence": confidence,
        "focus_symbols": focus_symbols,
        "top_opportunities": top_focus,
        "universal_strategy_map": universal_strategy_map,
        "preferred_structures": preferred_structures,
        "forbidden_structures": forbidden_structures,
        "max_new_entries": max_new_entries,
        "max_concurrent_trades": risk_cfg.get("max_concurrent_trades", 999),
        "max_deployed_capital_pct": risk_cfg.get("max_deployed_capital_pct", 70),
        "min_idle_liquidity_pct": risk_cfg.get("min_idle_liquidity_pct", 30),
        "min_risk_per_trade_usd": risk_cfg.get("min_risk_per_trade_usd", 50000),
        "max_risk_per_trade_usd": risk_cfg.get("max_risk_per_trade_usd", 100000),
        "autonomous_entries": exec_cfg.get("autonomous_entries", True),
        "autonomous_exits": exec_cfg.get("autonomous_exits", True),
        "owner_approval_required": exec_cfg.get("owner_approval_required", False),
        "reasons": reasons,
        "session_note": state.get("regime_view", {}).get("session_note", ""),
    }

    state["session_plan"] = plan

    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    return state
