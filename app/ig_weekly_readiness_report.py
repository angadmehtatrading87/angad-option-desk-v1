from app.ig_sunday_checklist_engine import run_sunday_checklist
from app.ig_decision_audit import summarize_decision_audit
from app.ig_anomaly_registry import list_anomalies

def build_weekly_readiness_report():
    checklist = run_sunday_checklist()
    audit = summarize_decision_audit()
    anomalies = list_anomalies(25)

    return {
        "checklist": checklist,
        "decision_audit": audit,
        "recent_anomalies": anomalies,
        "recommendation": (
            "hold_defensive"
            if checklist.get("summary", {}).get("deploy_verdict") == "NO_DEPLOY"
            else "watch_transition_closely"
        )
    }
