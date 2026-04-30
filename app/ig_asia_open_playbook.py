from app.ig_api_governor import get_ig_cached_snapshot
from app.ig_session_intelligence import get_ig_session_state


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def evaluate_asia_open_playbook(now=None, session_state=None):
    session_state = session_state or get_ig_session_state(now=now)

    snap = get_ig_cached_snapshot()
    rows = ((snap.get("positions") or {}).get("positions") or [])

    spreads = []
    pcts = []

    for r in rows:
        bid = _safe_float(r.get("bid"))
        offer = _safe_float(r.get("offer"))
        pct = abs(_safe_float(r.get("percentage_change")))
        if offer > 0 and bid > 0 and offer >= bid:
            spreads.append(offer - bid)
        pcts.append(pct)

    avg_spread = round(sum(spreads) / len(spreads), 6) if spreads else None
    avg_abs_pct_change = round(sum(pcts) / len(pcts), 6) if pcts else 0.0

    spread_quality = "tight"
    if avg_spread is None:
        spread_quality = "unknown"
    elif avg_spread >= 8:
        spread_quality = "wide"
    elif avg_spread >= 5:
        spread_quality = "acceptable"

    momentum_quality = "weak"
    if avg_abs_pct_change >= 0.35:
        momentum_quality = "strong"
    elif avg_abs_pct_change >= 0.12:
        momentum_quality = "moderate"

    session = session_state.get("session")
    market_open = bool(session_state.get("market_open"))
    liquidity = session_state.get("liquidity")

    probe_allowed = False
    scale_allowed = False
    size_multiplier = 0.0
    action_bias = "standby"
    notes = []

    if session == "asia" and market_open:
        if spread_quality in ("tight", "acceptable") and momentum_quality in ("moderate", "strong"):
            probe_allowed = True
            action_bias = "probe"
            size_multiplier = 0.35
            notes.append("Asia conditions acceptable for probing.")
        else:
            notes.append("Asia open spread too wide; do not engage.")
    elif session == "sunday_reopen_probe" and market_open:
        if spread_quality == "tight" and momentum_quality in ("moderate", "strong"):
            probe_allowed = True
            action_bias = "probe"
            size_multiplier = 0.25
            notes.append("Sunday reopen allows light probing.")
        else:
            notes.append("Sunday reopen conditions not clean enough.")
    else:
        notes.append("Asia playbook inactive outside Sunday/Asia windows.")

    if probe_allowed and spread_quality == "tight" and momentum_quality == "strong" and liquidity in ("medium", "high"):
        scale_allowed = True
        action_bias = "scale"
        size_multiplier = 0.75
        notes.append("Conditions strong enough to allow scaling.")

    return {
        "session": session,
        "market_open": market_open,
        "liquidity": liquidity,
        "avg_abs_pct_change": avg_abs_pct_change,
        "spread_quality": spread_quality,
        "momentum_quality": momentum_quality,
        "open_bias": "neutral",
        "probe_allowed": probe_allowed,
        "scale_allowed": scale_allowed,
        "size_multiplier": size_multiplier,
        "action_bias": action_bias,
        "notes": notes,
    }
