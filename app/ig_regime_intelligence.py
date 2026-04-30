from app.ig_api_governor import get_ig_cached_snapshot
from app.ig_session_intelligence import get_ig_session_state

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def classify_market_regime(positions=None, session_state=None):
    session_state = session_state or get_ig_session_state()
    snap = get_ig_cached_snapshot()
    rows = positions if positions is not None else ((snap.get("positions") or {}).get("positions") or [])

    if not rows:
        return {
            "regime": "inactive",
            "momentum_score": 0.0,
            "structure_score": 0.0,
            "conviction_score": 0.0,
            "notes": ["No live positions/market rows available."]
        }

    pct_vals = [_safe_float(r.get("percentage_change")) for r in rows]
    abs_pcts = [abs(x) for x in pct_vals]
    avg_abs_pct = sum(abs_pcts) / max(1, len(abs_pcts))

    tradeable_rows = [r for r in rows if r.get("market_status") in ("TRADEABLE", "EDITS_ONLY")]
    tradeable_ratio = len(tradeable_rows) / max(1, len(rows))

    direction_bias = 0
    for r in rows:
        pct = _safe_float(r.get("percentage_change"))
        if pct > 0:
            direction_bias += 1
        elif pct < 0:
            direction_bias -= 1

    notes = []
    regime = "range"
    momentum_score = 0.0
    structure_score = 0.0
    conviction_score = 0.0

    if avg_abs_pct >= 0.18 and abs(direction_bias) >= max(2, len(rows) // 3):
        regime = "trend"
        momentum_score = min(100.0, avg_abs_pct * 350.0)
        structure_score = min(100.0, 55.0 + abs(direction_bias) * 6.0)
        notes.append("Directional alignment and strong short-term movement.")
    elif avg_abs_pct >= 0.10 and tradeable_ratio >= 0.7:
        regime = "breakout_watch"
        momentum_score = min(100.0, avg_abs_pct * 280.0)
        structure_score = 55.0
        notes.append("Expanding movement, but not yet a fully clean trend.")
    elif avg_abs_pct <= 0.04:
        regime = "range"
        momentum_score = 20.0
        structure_score = 35.0
        notes.append("Low movement / drift / likely range conditions.")
    else:
        regime = "mixed"
        momentum_score = min(100.0, avg_abs_pct * 220.0)
        structure_score = 45.0
        notes.append("Mixed conditions, avoid overconfidence.")

    session = session_state.get("session")
    if session in ("london", "new_york", "london_friday"):
        conviction_boost = 10.0
        notes.append("High-quality session for confirmation.")
    elif session in ("asia", "asia_friday"):
        conviction_boost = 4.0
        notes.append("Asia session quality: moderate conviction.")
    elif session in ("sunday_reopen_probe", "late_us", "friday_reduction"):
        conviction_boost = -10.0
        notes.append("Session quality reduced; use smaller conviction.")
    elif session in ("weekend_closed", "friday_close_window"):
        conviction_boost = -25.0
        notes.append("Closed/flatten window.")
    else:
        conviction_boost = -5.0

    conviction_score = max(0.0, min(100.0, (momentum_score * 0.55) + (structure_score * 0.45) + conviction_boost))

    return {
        "regime": regime,
        "momentum_score": round(momentum_score, 2),
        "structure_score": round(structure_score, 2),
        "conviction_score": round(conviction_score, 2),
        "direction_bias": direction_bias,
        "avg_abs_pct_change": round(avg_abs_pct, 4),
        "tradeable_ratio": round(tradeable_ratio, 2),
        "notes": notes
    }

def get_entry_expression(regime_payload, session_state=None):
    session_state = session_state or get_ig_session_state()
    regime = regime_payload.get("regime")
    conviction = _safe_float(regime_payload.get("conviction_score"))
    session = session_state.get("session")

    probe_only = False
    size_multiplier = 1.0
    entry_style = "standard"
    aggressiveness = "normal"

    if session == "sunday_reopen_probe":
        probe_only = True
        size_multiplier = 0.35
        entry_style = "probe"
        aggressiveness = "low"
    elif session in ("weekend_closed", "friday_close_window"):
        probe_only = False
        size_multiplier = 0.0
        entry_style = "blocked"
        aggressiveness = "none"
    elif regime == "trend" and conviction >= 70:
        size_multiplier = 1.0
        entry_style = "trend_follow"
        aggressiveness = "high"
    elif regime == "breakout_watch":
        size_multiplier = 0.6
        entry_style = "breakout_probe"
        aggressiveness = "medium"
    elif regime == "range":
        size_multiplier = 0.3
        entry_style = "selective_only"
        aggressiveness = "low"
    else:
        size_multiplier = 0.5
        entry_style = "mixed_selective"
        aggressiveness = "medium"

    return {
        "probe_only": probe_only,
        "size_multiplier": round(size_multiplier, 2),
        "entry_style": entry_style,
        "aggressiveness": aggressiveness
    }
