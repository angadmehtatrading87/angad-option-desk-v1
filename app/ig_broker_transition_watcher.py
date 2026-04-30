from app.ig_session_intelligence import get_ig_session_state
from app.ig_api_governor import get_ig_cached_snapshot
from app.ig_close_reconciliation import reconcile_pending_closes, summarize_reconciliation

def evaluate_broker_transition():
    session_state = get_ig_session_state()
    snap = get_ig_cached_snapshot(force_refresh=True)
    recon = summarize_reconciliation()

    rows = ((snap.get("positions") or {}).get("positions") or [])
    statuses = sorted(set((r.get("market_status") or "UNKNOWN") for r in rows))

    all_tradeable = bool(rows) and all((r.get("market_status") == "TRADEABLE") for r in rows)
    any_edits_only = any((r.get("market_status") == "EDITS_ONLY") for r in rows)
    pending_closes = int(recon.get("pending_count", 0) or 0)

    transition_state = "stable_closed"
    if session_state.get("session") == "weekend_closed":
        transition_state = "stable_closed"
    elif session_state.get("session") == "sunday_reopen_probe":
        transition_state = "reopen_probe"
    elif all_tradeable:
        transition_state = "fully_tradeable"
    elif any_edits_only:
        transition_state = "edits_only_transition"

    deploy_gate_open = (
        session_state.get("market_open") and
        transition_state == "fully_tradeable" and
        pending_closes == 0
    )

    notes = []
    if pending_closes > 0:
        notes.append("Pending closes exist; do not allow fresh deployment yet.")
    if any_edits_only:
        notes.append("Broker still in EDITS_ONLY state; wait for full tradeability.")
    if transition_state == "fully_tradeable" and pending_closes == 0:
        notes.append("Broker state clean; deployment gate may open.")
    if transition_state == "reopen_probe":
        notes.append("Sunday reopen window detected; probe logic only.")

    return {
        "session_state": session_state,
        "transition_state": transition_state,
        "market_statuses": statuses,
        "pending_closes": pending_closes,
        "deploy_gate_open": deploy_gate_open,
        "broker_ok": snap.get("ok", False),
        "notes": notes
    }

def run_transition_reconciliation():
    recon = reconcile_pending_closes()
    watcher = evaluate_broker_transition()
    return {
        "ok": True,
        "reconciliation": recon,
        "watcher": watcher
    }
