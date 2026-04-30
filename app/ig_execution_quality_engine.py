from app.ig_live_book_source import get_unified_live_rows
from app.ig_close_reconciliation import summarize_reconciliation

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def _spread_for_row(row):
    bid = _safe_float(row.get("bid"), 0.0)
    offer = _safe_float(row.get("offer"), 0.0)
    if bid <= 0 or offer <= 0 or offer < bid:
        return None
    return offer - bid

def build_execution_quality():
    live = get_unified_live_rows()
    rows = live.get("rows", [])
    recon = summarize_reconciliation()

    spreads = []
    statuses = {}
    for r in rows:
        s = _spread_for_row(r)
        if s is not None:
            spreads.append(s)
        status = str(r.get("market_status") or "UNKNOWN")
        statuses[status] = statuses.get(status, 0) + 1

    avg_spread = round(sum(spreads) / len(spreads), 6) if spreads else None
    max_spread = round(max(spreads), 6) if spreads else None
    pending_closes = int(recon.get("pending_count", 0) or 0)
    confirmed_closes = int(recon.get("confirmed_count", 0) or 0)

    quality_score = 100.0
    notes = []

    if not live.get("broker_snapshot_ok", False):
        quality_score -= 30.0
        notes.append("Broker snapshot not fully reliable.")

    if statuses.get("EDITS_ONLY", 0) > 0:
        quality_score -= 30.0
        notes.append("Broker in EDITS_ONLY state.")

    if statuses.get("UNKNOWN", 0) > 0:
        quality_score -= 10.0
        notes.append("Unknown market status present.")

    if pending_closes >= 3:
        quality_score -= 25.0
        notes.append("Several pending closes are unresolved.")
    elif pending_closes >= 1:
        quality_score -= 12.0
        notes.append("Pending close reconciliation still active.")

    if avg_spread is not None:
        if avg_spread >= 8:
            quality_score -= 20.0
            notes.append("Average spread looks very wide.")
        elif avg_spread >= 4:
            quality_score -= 10.0
            notes.append("Average spread looks moderately wide.")

    quality_score = round(max(0.0, min(100.0, quality_score)), 2)

    if quality_score < 35:
        deployment_bias = "avoid"
        size_adjustment = 0.0
        should_delay = True
        should_block = True
    elif quality_score < 55:
        deployment_bias = "poor"
        size_adjustment = 0.5
        should_delay = True
        should_block = False
    elif quality_score < 75:
        deployment_bias = "cautious"
        size_adjustment = 0.8
        should_delay = False
        should_block = False
    else:
        deployment_bias = "good"
        size_adjustment = 1.0
        should_delay = False
        should_block = False

    return {
        "broker_snapshot_ok": live.get("broker_snapshot_ok", False),
        "market_status_counts": statuses,
        "avg_spread": avg_spread,
        "max_spread": max_spread,
        "pending_closes": pending_closes,
        "confirmed_closes": confirmed_closes,
        "quality_score": quality_score,
        "deployment_bias": deployment_bias,
        "size_adjustment": size_adjustment,
        "should_delay": should_delay,
        "should_block": should_block,
        "notes": notes,
        "source": live.get("source"),
    }
