from app.ig_decision_audit import summarize_decision_audit, list_decision_audits
from app.ig_audit_hygiene import stabilized_only

def build_threshold_recommendation():
    audit = summarize_decision_audit()
    stabilized = stabilized_only(list_decision_audits(500))
    recent = len(stabilized) if stabilized else audit.get("recent_count", 0)
    avg_score = round(sum(float(x.get("master_score", 0.0) or 0.0) for x in stabilized) / recent, 2) if stabilized and recent else audit.get("avg_master_score", 0.0)
    blocked = sum(1 for x in stabilized if x.get("should_block")) if stabilized else audit.get("blocked_count", 0)

    notes = []
    recommendation = "no_change"

    if recent >= 20 and avg_score < 20:
        recommendation = "consider_less_conservative_after_open_if_quality_improves"
        notes.append("System stayed highly defensive across many observations.")
    if blocked >= 10:
        notes.append("Frequent hard blocking observed; verify whether this is justified.")
    if recent < 10:
        notes.append("Observation history still thin.")

    return {
        "recommendation": recommendation,
        "notes": notes,
        "audit_summary": audit,
        "stabilized_observation_count": recent,
        "stabilized_only": bool(stabilized),
    }
