from app.ig_exit_doctrine import (
    classify_profit_state,
    evaluate_exit_bias,
    evaluate_giveback_protection,
)
from app.ig_exit_registry import (
    get_position_record,
    record_peak_profit,
    get_reentry_state,
)


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _risk_points(position):
    entry = _safe_float((position or {}).get("entry_level"))
    stop = _safe_float((position or {}).get("stop_level"))
    if entry and stop:
        return abs(entry - stop)
    return 10.0


def _infer_momentum_quality(position, context):
    pnl = _safe_float((position or {}).get("pnl_points"))
    avg_abs_pct_change = _safe_float((context or {}).get("avg_abs_pct_change"))
    if pnl > 0 and avg_abs_pct_change > 0.15:
        return "good"
    if avg_abs_pct_change <= 0.05:
        return "weak"
    return "mixed"


def _infer_spread_quality(position, context):
    spread_quality = (context or {}).get("spread_quality")
    if spread_quality:
        return spread_quality

    avg_spread = _safe_float((context or {}).get("avg_spread"))
    if avg_spread <= 4:
        return "tight"
    if avg_spread <= 8:
        return "acceptable"
    return "wide"


def build_profit_capture_decision(position, context=None):
    context = context or {}

    current_pnl = _safe_float((position or {}).get("pnl_points"))
    risk_points = _risk_points(position)

    rec = get_position_record(position)
    peak_before = _safe_float(rec.get("peak_pnl_points", 0.0))
    record_peak_profit(position, current_pnl)
    peak_after = max(peak_before, current_pnl)

    classification = classify_profit_state(current_pnl, risk_points)
    profit_state = classification["profit_state"]
    r_multiple = classification["r_multiple"]

    regime = context.get("regime") or "range"
    regime_conviction = _safe_float(context.get("regime_conviction"))
    session = context.get("session")
    duplicate_symbol = bool(context.get("duplicate_symbol"))
    heavy_book = bool(context.get("heavy_book"))
    book_fragility = _safe_float(context.get("book_fragility"))
    spread_quality = _infer_spread_quality(position, context)
    momentum_quality = _infer_momentum_quality(position, context)

    giveback = evaluate_giveback_protection(
        current_pnl_points=current_pnl,
        peak_pnl_points=peak_after,
        r_multiple=r_multiple,
    )

    reentry = get_reentry_state(position)

    if giveback.get("triggered"):
        return {
            "profit_state": profit_state,
            "r_multiple": r_multiple,
            "peak_pnl_points": round(peak_after, 4),
            "current_pnl_points": round(current_pnl, 4),
            "giveback_pct": giveback.get("giveback_pct"),
            "giveback_limit_pct": giveback.get("giveback_limit_pct"),
            "profit_capture_action": "CLOSE_FULL",
            "partial_fraction": 1.0,
            "trail_tight": False,
            "profit_capture_reason": ["peak_giveback_threshold_hit"],
            "reentry_state": reentry,
            "spread_quality": spread_quality,
            "momentum_quality": momentum_quality,
        }

    bias = evaluate_exit_bias(
        profit_state=profit_state,
        current_pnl_points=current_pnl,
        r_multiple=r_multiple,
        regime=regime,
        regime_conviction=regime_conviction,
        session=session,
        spread_quality=spread_quality,
        momentum_quality=momentum_quality,
        book_fragility=book_fragility,
        duplicate_symbol=duplicate_symbol,
        heavy_book=heavy_book,
    )

    return {
        "profit_state": profit_state,
        "r_multiple": r_multiple,
        "peak_pnl_points": round(peak_after, 4),
        "current_pnl_points": round(current_pnl, 4),
        "giveback_pct": giveback.get("giveback_pct"),
        "giveback_limit_pct": giveback.get("giveback_limit_pct"),
        "profit_capture_action": bias.get("action", "HOLD"),
        "partial_fraction": _safe_float(bias.get("partial_fraction")),
        "trail_tight": bool(bias.get("trail_tight")),
        "profit_capture_reason": bias.get("reasons", []),
        "reentry_state": reentry,
        "spread_quality": spread_quality,
        "momentum_quality": momentum_quality,
    }


def rank_profit_taking_candidates(positions, context=None):
    context = context or {}
    ranked = []

    duplicate_symbols = set(context.get("duplicate_symbols") or [])

    for p in positions or []:
        local_ctx = dict(context)
        local_ctx["duplicate_symbol"] = (p.get("epic") in duplicate_symbols)

        pc = build_profit_capture_decision(p, local_ctx)
        action = pc.get("profit_capture_action")

        if action not in ("CLOSE_FULL", "TRIM_PARTIAL", "TRAIL_TIGHT"):
            continue

        score = 0.0
        score += _safe_float(pc.get("current_pnl_points")) * 4.0
        score += _safe_float(pc.get("r_multiple")) * 25.0
        score += _safe_float(context.get("book_fragility")) * 0.5

        if pc.get("giveback_pct", 0.0) > 0:
            score += _safe_float(pc.get("giveback_pct")) * 100.0

        if p.get("epic") in duplicate_symbols:
            score += 15.0

        ranked.append({
            **p,
            "profit_capture": pc,
            "profit_capture_priority": round(score, 2),
        })

    ranked.sort(key=lambda x: x.get("profit_capture_priority", 0.0), reverse=True)
    return ranked
