from app.ig_market_hours_map import build_market_hours_map, should_run_deep_preopen, should_run_transition_watch
from app.ig_sunday_checklist_engine import run_sunday_checklist
from app.ig_decision_consistency_engine import evaluate_decision_consistency
from app.ig_live_observation_engine import log_live_observation
from app.ig_anomaly_registry import add_anomaly
from app.ig_weekly_readiness_report import build_weekly_readiness_report
from app.ig_threshold_recommendation_engine import build_threshold_recommendation

def run_sunday_supervisor():
    hours = build_market_hours_map()
    checklist = run_sunday_checklist()
    consistency = evaluate_decision_consistency()
    observation = log_live_observation()
    report = None
    threshold = None

    if not checklist.get("ok", True):
        add_anomaly("checklist_failure", "high", checklist.get("summary", {}))

    if not consistency.get("ok", True):
        add_anomaly("decision_inconsistency", "high", consistency)

    if should_run_deep_preopen():
        report = build_weekly_readiness_report()

    if should_run_transition_watch():
        threshold = build_threshold_recommendation()

    return {
        "ok": checklist.get("ok", True) and consistency.get("ok", True),
        "market_hours": hours,
        "checklist": checklist,
        "consistency": consistency,
        "observation": observation,
        "weekly_report": report,
        "threshold_recommendation": threshold,
    }
