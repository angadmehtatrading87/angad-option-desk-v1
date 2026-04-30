import os
from app.ig_smart_trade_brain import evaluate_live_positions
from app.ig_adapter import IGAdapter
from app.ig_decision_engine import build_ig_decisions
from app.ig_api_governor import get_ig_cached_snapshot
from app.ig_learning_memory import summarize_memory, latest_daily_review
from app.ig_execution_sizing import get_execution_sizing_plan
from app.ig_forced_flatten_controller import build_forced_flatten_plan
from app.ig_throttle_guard import throttle_status
from app.ig_close_reconciliation import summarize_reconciliation
from app.ig_broker_transition_watcher import evaluate_broker_transition
from app.ig_monday_monitor import build_monday_monitor
from app.ig_outcome_learning_engine import sync_open_trade_context, score_reconciled_outcomes
from app.ig_adaptive_review_engine import build_adaptive_review

def get_live_positions():
    snap = get_ig_cached_snapshot()
    pos = snap.get("positions", {}) or {}
    if not pos.get("ok"):
        return {"ok": False, "reason": "cached_positions_failed", "positions": []}

    return {"ok": True, "positions": pos.get("positions", [])}


def _transition_worker_hint():
    return {
        "service_name": "angad-ig-transition.service",
        "expected_role": "automatic pending-close watcher and broker transition reconciler"
    }

def takeover_view():
    positions = get_live_positions()
    decisions = build_ig_decisions()
    smart = evaluate_live_positions()

    return {
        "positions": positions,
        "decisions": decisions,
        "managed_positions": smart.get("managed_positions", []),
        "reduced_risk_mode": smart.get("reduced_risk_mode", False),
        "profit_harvest_mode": smart.get("profit_harvest_mode", False),
        "account_snapshot": smart.get("account_snapshot", {}),
        "session_state": smart.get("session_state", {}),
        "carry_policy": smart.get("carry_policy", {}),
        "regime_state": smart.get("regime_state", {}),
        "entry_expression": smart.get("entry_expression", {}),
        "asia_playbook": smart.get("asia_playbook", {}),
        "execution_sizing": get_execution_sizing_plan(),
        "forced_flatten_plan": build_forced_flatten_plan(),
        "throttle_status": throttle_status(),
        "close_reconciliation": summarize_reconciliation(),
        "broker_transition": evaluate_broker_transition(),
        "monday_monitor": build_monday_monitor(),
        "transition_worker": _transition_worker_hint(),
        "learning_summary": summarize_memory(),
        "latest_daily_review": latest_daily_review(),
        "outcome_sync": sync_open_trade_context(),
        "outcome_scoring": score_reconciled_outcomes(),
        "adaptive_review": build_adaptive_review()
    }
