from app.ig_self_tuning_engine import build_self_tuning_decision

def evaluate_decision_consistency():
    st = build_self_tuning_decision()
    adaptive = st.get("adaptive_behavior", {}) or {}
    portfolio = st.get("portfolio_intelligence", {}) or {}
    execq = st.get("execution_quality", {}) or {}
    perception = st.get("market_perception", {}) or {}

    issues = []

    if st.get("deploy_verdict") == "ALLOW_SCALE" and execq.get("deployment_bias") in ("poor", "avoid", "cautious"):
        issues.append("scale_allowed_while_execution_weak")
    if st.get("deploy_verdict") in ("ALLOW_SCALE", "ALLOW_PROBE") and portfolio.get("fragility_score", 0) >= 60:
        issues.append("deployment_allowed_while_portfolio_fragile")
    if st.get("deploy_verdict") in ("ALLOW_SCALE", "ALLOW_PROBE") and perception.get("deployment_bias") == "defensive":
        issues.append("deployment_allowed_while_perception_defensive")
    if st.get("deploy_verdict") in ("ALLOW_SCALE", "ALLOW_PROBE") and adaptive.get("deployment_bias") == "defensive":
        issues.append("deployment_allowed_while_adaptive_defensive")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "verdict": st.get("deploy_verdict"),
        "master_score": st.get("master_score"),
    }
