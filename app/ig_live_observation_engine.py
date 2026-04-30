from app.ig_self_tuning_engine import build_self_tuning_decision
from app.ig_decision_audit import add_decision_audit, summarize_decision_audit

def log_live_observation(epic=None, session_override=None, regime_override=None, entry_style_override=None):
    st = build_self_tuning_decision(
        epic=epic,
        session_override=session_override,
        regime_override=regime_override,
        entry_style_override=entry_style_override
    )

    session_state = st.get("session_state", {}) or {}
    regime_state = st.get("regime_state", {}) or {}
    adaptive = st.get("adaptive_behavior", {}) or {}
    portfolio = st.get("portfolio_intelligence", {}) or {}
    execq = st.get("execution_quality", {}) or {}
    perception = st.get("market_perception", {}) or {}

    row = add_decision_audit({
        "epic": epic,
        "session": session_state.get("session"),
        "weekday": session_state.get("weekday"),
        "market_open": session_state.get("market_open"),
        "regime": regime_state.get("regime"),
        "regime_conviction": regime_state.get("conviction_score"),
        "deploy_verdict": st.get("deploy_verdict"),
        "threshold_state": st.get("threshold_state"),
        "master_score": st.get("master_score"),
        "final_size_multiplier": st.get("final_size_multiplier"),
        "final_confidence_adjustment": st.get("final_confidence_adjustment"),
        "should_block": st.get("should_block"),
        "block_reasons": st.get("block_reasons", []),
        "adaptive_bias": adaptive.get("deployment_bias"),
        "portfolio_bias": portfolio.get("deployment_bias"),
        "execution_bias": execq.get("deployment_bias"),
        "perception_bias": perception.get("deployment_bias"),
        "portfolio_fragility": portfolio.get("fragility_score"),
        "execution_quality_score": execq.get("quality_score"),
        "perception_state": perception.get("perception_state"),
        "notes": st.get("notes", []),
    })

    return {
        "ok": True,
        "logged": row,
        "summary": summarize_decision_audit()
    }
