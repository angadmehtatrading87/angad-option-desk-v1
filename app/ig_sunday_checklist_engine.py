from app.ig_market_hours_map import build_market_hours_map
from app.ig_live_book_source import get_unified_live_rows
from app.ig_portfolio_intelligence import build_portfolio_intelligence
from app.ig_execution_quality_engine import build_execution_quality
from app.ig_market_perception_engine import build_market_perception
from app.ig_self_tuning_engine import build_self_tuning_decision
from app.ig_decision_audit import summarize_decision_audit
from app.ig_close_reconciliation import summarize_reconciliation
from app.ig_transition_worker_hint import transition_worker_hint_safe
from app.ig_service_health import service_health_snapshot

def _section(name, status, notes=None, data=None):
    return {
        "name": name,
        "status": status,
        "notes": notes or [],
        "data": data or {}
    }

def _combine_status(stats):
    if "FAIL" in stats:
        return "FAIL"
    if "WARN" in stats:
        return "WARN"
    return "PASS"

def run_sunday_checklist():
    hours = build_market_hours_map()
    live = get_unified_live_rows()
    portfolio = build_portfolio_intelligence()
    execq = build_execution_quality()
    perception = build_market_perception()
    tuning = build_self_tuning_decision()
    audit = summarize_decision_audit()
    recon = summarize_reconciliation()
    svc = service_health_snapshot()
    transition = transition_worker_hint_safe()

    sections = []

    infra_notes = []
    infra_status = "PASS"
    for k, v in (svc.get("services") or {}).items():
        if not v.get("active", False):
            infra_status = "WARN"
            infra_notes.append(f"{k} not active.")
    sections.append(_section("infrastructure_health", infra_status, infra_notes, svc))

    active_phase = (hours.get("phase") in ("sunday_preopen", "forex_transition_watch", "monday_forex_open_window", "monday_index_transition_window"))
    broker_status = "PASS" if live.get("ok") and live.get("broker_snapshot_ok") else ("FAIL" if active_phase else "WARN")
    broker_notes = []
    if not live.get("ok"):
        broker_notes.append("Unified live rows unavailable.")
    if live.get("source") != "cached_snapshot":
        broker_notes.append(f"Using fallback source: {live.get('source')}.")
    if not active_phase:
        broker_notes.append("Outside active Sunday/Monday supervision window; degrade to WARN, not FAIL.")
    sections.append(_section("broker_connectivity_and_data", broker_status, broker_notes, {
        "live_source": live.get("source"),
        "row_count": len(live.get("rows") or []),
        "account": live.get("account"),
    }))

    recon_status = "PASS"
    recon_notes = []
    if (recon.get("pending_count") or 0) > 0:
        recon_status = "WARN"
        recon_notes.append("Pending close reconciliation exists.")
    sections.append(_section("reconciliation_control", recon_status, recon_notes, recon))

    port_status = "PASS"
    port_notes = list(portfolio.get("notes") or [])
    if portfolio.get("fragility_score", 0) >= 55:
        port_status = "WARN"
    sections.append(_section("portfolio_shape", port_status, port_notes, portfolio))

    exec_status = "PASS"
    exec_notes = list(execq.get("notes") or [])
    if execq.get("quality_score", 0) < 55:
        exec_status = "WARN"
    if execq.get("should_block"):
        exec_status = "FAIL"
    sections.append(_section("execution_environment", exec_status, exec_notes, execq))

    percept_status = "PASS"
    percept_notes = list(perception.get("notes") or [])
    if perception.get("deployment_bias") in ("defensive", "cautious"):
        percept_status = "WARN"
    sections.append(_section("market_perception", percept_status, percept_notes, perception))

    tune_status = "PASS"
    tune_notes = list(tuning.get("notes") or [])
    if tuning.get("deploy_verdict") == "NO_DEPLOY":
        tune_status = "WARN"
    if tuning.get("should_block"):
        tune_status = "FAIL"
    sections.append(_section("self_tuning_decision", tune_status, tune_notes, {
        "master_score": tuning.get("master_score"),
        "deploy_verdict": tuning.get("deploy_verdict"),
        "threshold_state": tuning.get("threshold_state"),
        "final_size_multiplier": tuning.get("final_size_multiplier"),
        "block_reasons": tuning.get("block_reasons"),
    }))

    audit_status = "PASS"
    audit_notes = []
    if (audit.get("recent_count") or 0) == 0:
        audit_status = "WARN"
        audit_notes.append("Decision audit has no recent observations.")
    sections.append(_section("audit_continuity", audit_status, audit_notes, audit))

    overall = _combine_status([s["status"] for s in sections])

    return {
        "ok": overall != "FAIL",
        "overall_status": overall,
        "market_hours": hours,
        "sections": sections,
        "transition_worker": transition,
        "summary": {
            "live_rows": len(live.get("rows") or []),
            "pending_closes": recon.get("pending_count", 0),
            "portfolio_fragility": portfolio.get("fragility_score", 0.0),
            "execution_quality_score": execq.get("quality_score", 0.0),
            "perception_state": perception.get("perception_state"),
            "deploy_verdict": tuning.get("deploy_verdict"),
            "master_score": tuning.get("master_score"),
        }
    }
