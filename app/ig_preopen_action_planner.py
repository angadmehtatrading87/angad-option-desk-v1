from app.ig_market_hours_map import build_market_hours_map
from app.ig_portfolio_intelligence import build_portfolio_intelligence
from app.ig_execution_quality_engine import build_execution_quality
from app.ig_self_tuning_engine import build_self_tuning_decision
from app.ig_smart_trade_brain import evaluate_live_positions
from app.ig_preopen_window_policy import build_preopen_window_policy

def _choose_candidates(managed, limit=3):
    if not managed:
        return []
    ranked = sorted(
        managed,
        key=lambda x: float(x.get("close_priority", 0.0) or 0.0),
        reverse=True
    )
    return ranked[:limit]

def build_preopen_action_plan(now=None):
    hours = build_market_hours_map(now=now)
    arming_policy = build_preopen_window_policy(now=now)
    portfolio = build_portfolio_intelligence()
    execq = build_execution_quality()
    tuning = build_self_tuning_decision(now=now)
    smart = evaluate_live_positions()

    managed = smart.get("managed_positions", []) or []
    candidates = _choose_candidates(managed, limit=3)

    action_type = "NO_ACTION"
    rationale = []
    safe_to_execute = False

    fragility = float(portfolio.get("fragility_score", 0.0) or 0.0)
    quality = float(execq.get("quality_score", 0.0) or 0.0)
    verdict = str(tuning.get("deploy_verdict", ""))

    if fragility >= 60:
        action_type = "REDUCE_RISK"
        rationale.append("Portfolio fragility elevated.")
    if fragility >= 70 and quality >= 50 and managed:
        action_type = "FORCE_FLATTEN_BATCH"
        rationale.append("Portfolio extremely fragile with live managed positions.")
    if verdict == "NO_DEPLOY":
        rationale.append("Self-tuning forbids fresh deployment.")

    if arming_policy.get("armed") and arming_policy.get("max_batch", 0) > 0:
        if action_type in ("REDUCE_RISK", "FORCE_FLATTEN_BATCH"):
            safe_to_execute = True

    return {
        "market_hours": hours,
        "arming_policy": {
            "timestamp": arming_policy.get("timestamp"),
            "market_hours": hours,
            "arming_state": "armed" if arming_policy.get("armed") else "disarmed",
            "execution_allowed": bool(arming_policy.get("armed")),
            "max_batch": int(arming_policy.get("max_batch", 0) or 0),
            "cooldown_seconds": 0,
            "notes": arming_policy.get("notes", []),
            "stage": arming_policy.get("stage"),
            "force_flatten_allowed": arming_policy.get("force_flatten_allowed", False),
        },
        "portfolio_intelligence": portfolio,
        "execution_quality": execq,
        "self_tuning": tuning,
        "action_type": action_type,
        "safe_to_execute": safe_to_execute,
        "rationale": rationale,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
