from app.ig_decision_audit import list_decision_audits

STABILIZED_CUTOFF = "2026-04-25T19:40:24+04:00"

def classify_audit_entry(x):
    ts = str(x.get("timestamp") or "")
    stabilized = ts >= STABILIZED_CUTOFF
    return {
        **x,
        "audit_generation": "stabilized_v1" if stabilized else "legacy_v0"
    }

def build_hygiene_summary(limit=500):
    items = [classify_audit_entry(x) for x in list_decision_audits(limit)]
    legacy = [x for x in items if x.get("audit_generation") == "legacy_v0"]
    stabilized = [x for x in items if x.get("audit_generation") == "stabilized_v1"]

    return {
        "total_reviewed": len(items),
        "legacy_count": len(legacy),
        "stabilized_count": len(stabilized),
        "latest_stabilized": stabilized[-20:],
        "latest_legacy": legacy[-20:],
    }

def stabilized_only(items):
    return [classify_audit_entry(x) for x in items if classify_audit_entry(x).get("audit_generation") == "stabilized_v1"]
