from app.ig_session_intelligence import get_ig_session_state

def get_no_trade_reasons():
    s = get_ig_session_state()
    reasons = []

    if not s.get("market_open"):
        reasons.append("market_closed_or_off_session")

    entry_mode = s.get("entry_mode")
    if entry_mode == "blocked":
        reasons.append("entry_blocked_by_session")
    elif entry_mode == "probe_only":
        reasons.append("probe_only_session")
    elif entry_mode == "reduced":
        reasons.append("reduced_risk_session")

    liquidity = s.get("liquidity")
    if liquidity in ("low", "thin", "closed"):
        reasons.append(f"liquidity_{liquidity}")

    return {
        "session_state": s,
        "reasons": reasons
    }
