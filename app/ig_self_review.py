from app.ig_learning_memory import summarize_memory, write_daily_review
from app.ig_session_intelligence import get_ig_session_state
from app.ig_api_governor import get_ig_cached_snapshot

def build_daily_self_review():
    mem = summarize_memory()
    session_state = get_ig_session_state()
    snap = get_ig_cached_snapshot()

    by_session = mem.get("by_session", {})
    by_symbol = mem.get("by_symbol", {})
    recent = mem.get("recent_trades", [])

    strongest_sessions = sorted(
        [{"session": k, **v} for k, v in by_session.items()],
        key=lambda x: x.get("pnl", 0.0),
        reverse=True
    )[:5]

    weakest_sessions = sorted(
        [{"session": k, **v} for k, v in by_session.items()],
        key=lambda x: x.get("pnl", 0.0)
    )[:5]

    strongest_symbols = sorted(
        [{"symbol": k, **v} for k, v in by_symbol.items()],
        key=lambda x: x.get("pnl", 0.0),
        reverse=True
    )[:5]

    weakest_symbols = sorted(
        [{"symbol": k, **v} for k, v in by_symbol.items()],
        key=lambda x: x.get("pnl", 0.0)
    )[:5]

    review = {
        "session_state": session_state,
        "broker_snapshot_ok": snap.get("ok", False),
        "open_positions": ((snap.get("positions") or {}).get("count") or 0),
        "trade_count": mem.get("trade_count", 0),
        "strongest_sessions": strongest_sessions,
        "weakest_sessions": weakest_sessions,
        "strongest_symbols": strongest_symbols,
        "weakest_symbols": weakest_symbols,
        "recent_trade_count": len(recent),
        "notes": []
    }

    if not snap.get("ok", False):
        review["notes"].append("Broker snapshot unavailable or throttled during review.")
    if session_state.get("session") == "weekend_closed":
        review["notes"].append("Weekend closed; focus on review and planning, not execution.")
    if not strongest_sessions:
        review["notes"].append("Not enough learning history yet; continue building memory.")
    else:
        review["notes"].append("Use strongest sessions/symbols to guide next-week prioritization.")

    return review

def run_daily_self_review():
    review = build_daily_self_review()
    write_daily_review(review)
    return review
