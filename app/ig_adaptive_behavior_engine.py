from app.ig_adaptive_review_engine import build_adaptive_review

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def _bucket_lookup(rows, name):
    name = str(name or "unknown")
    for r in rows or []:
        if str(r.get("name")) == name:
            return r
    return None

def _edge_score(row):
    if not row:
        return 0.0
    count = _safe_float(row.get("count", 0))
    wins = _safe_float(row.get("wins", 0))
    pnl = _safe_float(row.get("pnl", 0.0))
    if count <= 0:
        return 0.0
    win_rate = wins / count
    return (win_rate * 50.0) + pnl

def build_adaptive_behavior_context(epic=None, session=None, regime=None, entry_style=None):
    review = build_adaptive_review()

    sym_row = _bucket_lookup(review.get("best_symbols", []) + review.get("worst_symbols", []), epic or "UNKNOWN")
    ses_row = _bucket_lookup(review.get("best_sessions", []) + review.get("worst_sessions", []), session or "unknown")
    reg_row = _bucket_lookup(review.get("best_regimes", []) + review.get("worst_regimes", []), regime or "unknown")
    sty_row = _bucket_lookup(review.get("best_entry_styles", []) + review.get("worst_entry_styles", []), entry_style or "unknown")

    sym_score = _edge_score(sym_row)
    ses_score = _edge_score(ses_row)
    reg_score = _edge_score(reg_row)
    sty_score = _edge_score(sty_row)

    completed = int(((review.get("scorecards") or {}).get("completed_count")) or 0)

    notes = []
    behavior = {
        "adaptive_enabled": completed >= 3,
        "completed_history": completed,
        "symbol_edge_score": round(sym_score, 2),
        "session_edge_score": round(ses_score, 2),
        "regime_edge_score": round(reg_score, 2),
        "style_edge_score": round(sty_score, 2),
        "size_adjustment": 1.0,
        "confidence_adjustment": 0.0,
        "deployment_bias": "neutral",
        "should_reduce": False,
        "should_block": False,
        "notes": notes,
    }

    if completed < 3:
        behavior["adaptive_enabled"] = False
        behavior["size_adjustment"] = 0.9
        notes.append("History too thin; apply mild caution only.")
        return behavior

    total_score = sym_score + ses_score + reg_score + sty_score

    if total_score <= -20:
        behavior["size_adjustment"] = 0.5
        behavior["confidence_adjustment"] = -12.0
        behavior["deployment_bias"] = "defensive"
        behavior["should_reduce"] = True
        notes.append("Context historically weak; reduce aggressively.")
    elif total_score <= -5:
        behavior["size_adjustment"] = 0.75
        behavior["confidence_adjustment"] = -6.0
        behavior["deployment_bias"] = "cautious"
        behavior["should_reduce"] = True
        notes.append("Context mildly weak; reduce size.")
    elif total_score >= 20:
        behavior["size_adjustment"] = 1.2
        behavior["confidence_adjustment"] = 8.0
        behavior["deployment_bias"] = "favorable"
        notes.append("Context historically favorable; modest boost allowed.")
    elif total_score >= 8:
        behavior["size_adjustment"] = 1.1
        behavior["confidence_adjustment"] = 4.0
        behavior["deployment_bias"] = "positive"
        notes.append("Context positive; slight boost allowed.")
    else:
        behavior["size_adjustment"] = 1.0
        behavior["confidence_adjustment"] = 0.0
        behavior["deployment_bias"] = "neutral"
        notes.append("No meaningful adaptive edge yet.")

    if sym_row and _safe_float(sym_row.get("count", 0)) >= 4 and _safe_float(sym_row.get("pnl", 0.0)) < -15:
        behavior["should_block"] = True
        behavior["deployment_bias"] = "blocked_symbol"
        behavior["size_adjustment"] = 0.0
        notes.append("Symbol-level history materially weak; block deployment.")

    return behavior
