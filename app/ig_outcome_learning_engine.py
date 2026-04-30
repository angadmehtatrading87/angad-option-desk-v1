from app.ig_close_reconciliation import all_reconciliation_items
from app.ig_trade_scorecard import upsert_scorecard, summarize_scorecards

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def sync_open_trade_context(takeover=None):
    takeover = takeover or {}
    managed = takeover.get("managed_positions", []) or []
    session_state = takeover.get("session_state", {}) or {}

    synced = []
    for p in managed:
        deal_id = p.get("deal_id")
        if not deal_id:
            continue

        row = upsert_scorecard(deal_id, {
            "epic": p.get("epic"),
            "direction": p.get("direction"),
            "entry_session": session_state.get("session"),
            "entry_weekday": session_state.get("weekday"),
            "entry_regime": p.get("regime"),
            "entry_regime_conviction": p.get("regime_conviction"),
            "entry_style": p.get("entry_style"),
            "asia_action_bias": p.get("asia_action_bias"),
            "entry_size": p.get("size"),
            "entry_level": p.get("entry_level"),
            "latest_mark_level": p.get("mark_level"),
            "latest_pnl_points": p.get("pnl_points"),
            "management_tags": p.get("management_tags", []),
            "scorecard_state": "OPEN_TRACKED"
        })
        synced.append(row)

    return {"ok": True, "synced_count": len(synced), "items": synced[-20:]}

def score_reconciled_outcomes():
    recon = all_reconciliation_items()
    changed = []

    for r in recon:
        deal_id = r.get("deal_id")
        if not deal_id:
            continue

        status = r.get("status")
        pnl = _safe_float((r.get("meta") or {}).get("pnl_points", 0.0))

        if status == "CONFIRMED_CLOSED":
            outcome = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "SCRATCH")
            row = upsert_scorecard(deal_id, {
                "close_deal_reference": r.get("deal_reference"),
                "close_size": r.get("close_size"),
                "requested_action": r.get("requested_action"),
                "realized_pnl_points": pnl,
                "outcome_state": outcome,
                "scorecard_state": "CLOSED_SCORED"
            })
            changed.append(row)
        elif status == "PENDING_BROKER":
            row = upsert_scorecard(deal_id, {
                "close_deal_reference": r.get("deal_reference"),
                "close_size": r.get("close_size"),
                "requested_action": r.get("requested_action"),
                "scorecard_state": "PENDING_CLOSE_CONFIRMATION"
            })
            changed.append(row)

    return {
        "ok": True,
        "changed_count": len(changed),
        "items": changed[-20:],
        "summary": summarize_scorecards()
    }
