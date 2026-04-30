from app.ig_sunday_checklist_engine import run_sunday_checklist
from app.ig_decision_consistency_engine import evaluate_decision_consistency
from app.ig_decision_audit import summarize_decision_audit, list_decision_audits
from app.ig_audit_hygiene import build_hygiene_summary, stabilized_only
from app.ig_threshold_recommendation_engine import build_threshold_recommendation
from app.ig_anomaly_registry import list_anomalies

def _summarize_stabilized(items):
    verdict_counts = {}
    threshold_counts = {}
    avg_score = 0.0
    avg_size = 0.0

    for x in items:
        verdict = str(x.get("deploy_verdict", "UNKNOWN"))
        threshold = str(x.get("threshold_state", "UNKNOWN"))
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        threshold_counts[threshold] = threshold_counts.get(threshold, 0) + 1
        avg_score += float(x.get("master_score", 0.0) or 0.0)
        avg_size += float(x.get("final_size_multiplier", 0.0) or 0.0)

    n = len(items)
    if n:
        avg_score = round(avg_score / n, 2)
        avg_size = round(avg_size / n, 4)

    return {
        "count": n,
        "verdict_counts": verdict_counts,
        "threshold_counts": threshold_counts,
        "avg_master_score": avg_score,
        "avg_final_size_multiplier": avg_size,
        "latest_items": items[-20:],
    }

def build_sunday_final_report():
    checklist = run_sunday_checklist()
    consistency = evaluate_decision_consistency()
    audit_summary = summarize_decision_audit()
    hygiene = build_hygiene_summary()
    stabilized = stabilized_only(list_decision_audits(500))
    stabilized_summary = _summarize_stabilized(stabilized)
    threshold = build_threshold_recommendation()
    anomalies = list_anomalies(50)

    recommendation = "hold_defensive"
    if checklist.get("summary", {}).get("deploy_verdict") in ("ALLOW_PROBE", "ALLOW_SCALE"):
        recommendation = "transition_to_live_supervision"

    return {
        "checklist": checklist,
        "consistency": consistency,
        "audit_hygiene": hygiene,
        "stabilized_audit_summary": stabilized_summary,
        "full_audit_summary": audit_summary,
        "threshold_recommendation": threshold,
        "recent_anomalies": anomalies,
        "final_recommendation": recommendation,
    }
