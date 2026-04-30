from app.ig_execution_sizing import get_execution_sizing_plan

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def build_self_tuning_decision(now=None):
    try:
        sizing = get_execution_sizing_plan(now=now) or {}
    except Exception as e:
        sizing = {
            "adaptive_behavior": {},
            "portfolio_intelligence": {},
            "execution_quality": {},
            "market_perception": {},
            "entry_expression": {},
            "asia_playbook": {},
            "regime_state": {},
            "session_state": {},
            "block_reasons": [f"self_tuning_input_error:{type(e).__name__}"],
        }

    adaptive = sizing.get("adaptive_behavior", {}) or {}
    portfolio = sizing.get("portfolio_intelligence", {}) or {}
    execq = sizing.get("execution_quality", {}) or {}
    perception = sizing.get("market_perception", {}) or {}
    expr = sizing.get("entry_expression", {}) or {}
    asia = sizing.get("asia_playbook", {}) or {}
    regime = sizing.get("regime_state", {}) or {}
    session_state = sizing.get("session_state", {}) or {}

    notes = []
    score = 50.0

    score += _safe_float(adaptive.get("confidence_adjustment", 0.0))
    score += (_safe_float(execq.get("quality_score", 0.0)) - 50.0) * 0.30
    score += (_safe_float(regime.get("conviction_score", 0.0)) - 20.0) * 0.40
    score += (_safe_float(perception.get("expansion_score", 0.0)) - 5.0) * 0.25
    score -= _safe_float(portfolio.get("fragility_score", 0.0)) * 0.35

    if adaptive.get("should_reduce"):
        score -= 8.0
        notes.append("Adaptive layer is defensive.")
    if portfolio.get("should_reduce"):
        score -= 10.0
        notes.append("Portfolio layer is defensive.")
    if execq.get("should_delay"):
        score -= 6.0
        notes.append("Execution quality suggests caution.")
    if perception.get("should_reduce"):
        score -= 5.0
        notes.append("Market perception suggests caution.")

    if asia.get("probe_allowed"):
        score += 4.0
        notes.append("Asia playbook allows probing.")
    if asia.get("scale_allowed"):
        score += 6.0
        notes.append("Asia playbook allows scaling.")

    if expr.get("entry_style") == "blocked":
        score -= 20.0
        notes.append("Entry expression blocked.")
    elif expr.get("entry_style") == "probe":
        score -= 4.0
        notes.append("Probe-only environment.")
    elif expr.get("entry_style") == "normal":
        score += 2.0
    elif expr.get("entry_style") == "aggressive":
        score += 5.0

    if session_state.get("market_open") is False:
        score -= 20.0
        notes.append("Market not open.")
    if session_state.get("session") == "weekend_closed":
        score -= 15.0
        notes.append("Weekend closed state.")

    score = round(max(0.0, min(100.0, score)), 2)

    raw_size = 1.0
    raw_size *= _safe_float(adaptive.get("size_adjustment", 1.0), 1.0)
    raw_size *= _safe_float(portfolio.get("size_adjustment", 1.0), 1.0)
    raw_size *= _safe_float(execq.get("size_adjustment", 1.0), 1.0)
    raw_size *= _safe_float(perception.get("size_adjustment", 1.0), 1.0)

    if expr.get("size_multiplier") is not None:
        raw_size *= _safe_float(expr.get("size_multiplier", 1.0), 1.0)
    if asia.get("size_multiplier") is not None:
        raw_size *= _safe_float(asia.get("size_multiplier", 1.0), 1.0)

    raw_size = round(max(0.0, min(1.5, raw_size)), 4)

    should_block = False
    block_reasons = list(sizing.get("block_reasons", []) or [])

    if adaptive.get("should_block"):
        should_block = True
        block_reasons.append("adaptive_hard_block")
    if portfolio.get("should_block_new"):
        should_block = True
        block_reasons.append("portfolio_hard_block")
    if execq.get("should_block"):
        should_block = True
        block_reasons.append("execution_quality_hard_block")
    if perception.get("should_block"):
        should_block = True
        block_reasons.append("market_perception_hard_block")

    threshold_state = "blocked"
    deploy_verdict = "NO_DEPLOY"
    allow_probe = False
    allow_scale = False

    if not should_block:
        if score >= 75 and raw_size >= 0.85:
            threshold_state = "high_quality"
            deploy_verdict = "ALLOW_SCALE"
            allow_probe = True
            allow_scale = True
        elif score >= 58 and raw_size >= 0.45:
            threshold_state = "selective"
            deploy_verdict = "ALLOW_PROBE"
            allow_probe = True
            allow_scale = False
        else:
            threshold_state = "cautious"
            deploy_verdict = "NO_DEPLOY"
    else:
        threshold_state = "blocked"
        deploy_verdict = "NO_DEPLOY"

    final_confidence_adjustment = round(
        _safe_float(adaptive.get("confidence_adjustment", 0.0), 0.0)
        + ((_safe_float(execq.get("quality_score", 50.0), 50.0) - 50.0) * 0.10)
        - (_safe_float(portfolio.get("fragility_score", 0.0), 0.0) * 0.10),
        2
    )

    return {
        "master_score": score,
        "deploy_verdict": deploy_verdict,
        "threshold_state": threshold_state,
        "final_size_multiplier": raw_size,
        "final_confidence_adjustment": final_confidence_adjustment,
        "allow_probe": allow_probe,
        "allow_scale": allow_scale,
        "should_block": should_block,
        "block_reasons": sorted(set(block_reasons)),
        "notes": notes,
        "session_state": session_state,
        "regime_state": regime,
        "entry_expression": expr,
        "asia_playbook": asia,
        "adaptive_behavior": adaptive,
        "portfolio_intelligence": portfolio,
        "execution_quality": execq,
        "market_perception": perception,
    }
