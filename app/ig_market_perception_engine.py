from app.ig_live_book_source import get_unified_live_rows

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def build_market_perception():
    live = get_unified_live_rows()
    rows = live.get("rows", [])

    if not rows:
        return {
            "broker_snapshot_ok": live.get("broker_snapshot_ok", False),
            "perception_state": "inactive",
            "avg_abs_pct_change": 0.0,
            "avg_spread": None,
            "pressure_score": 0.0,
            "expansion_score": 0.0,
            "breakout_bias": "none",
            "directional_pressure": "neutral",
            "deployment_bias": "neutral",
            "size_adjustment": 1.0,
            "should_reduce": False,
            "should_block": False,
            "notes": ["No rows available for perception."],
            "source": live.get("source")
        }

    pct_changes = []
    spreads = []
    bullish = 0.0
    bearish = 0.0
    tradeable = 0
    edits_only = 0

    for r in rows:
        pct = _safe_float(r.get("percentage_change"), 0.0)
        pct_changes.append(abs(pct))
        if pct > 0:
            bullish += pct
        elif pct < 0:
            bearish += abs(pct)

        bid = _safe_float(r.get("bid"), 0.0)
        offer = _safe_float(r.get("offer"), 0.0)
        if bid > 0 and offer > 0 and offer >= bid:
            spreads.append(offer - bid)

        status = str(r.get("market_status") or "")
        if status == "TRADEABLE":
            tradeable += 1
        elif status == "EDITS_ONLY":
            edits_only += 1

    avg_abs_pct_change = round(sum(pct_changes) / len(pct_changes), 4) if pct_changes else 0.0
    avg_spread = round(sum(spreads) / len(spreads), 6) if spreads else None

    pressure_score = round(abs(bullish - bearish) * 100.0, 2)
    expansion_score = round(avg_abs_pct_change * 100.0, 2)

    directional_pressure = "neutral"
    if bullish > bearish * 1.5 and bullish > 0:
        directional_pressure = "bullish"
    elif bearish > bullish * 1.5 and bearish > 0:
        directional_pressure = "bearish"

    breakout_bias = "none"
    if avg_abs_pct_change >= 0.25:
        breakout_bias = "possible_breakout"
    elif avg_abs_pct_change <= 0.05:
        breakout_bias = "compression"

    notes = []
    perception_state = "balanced"

    if edits_only > 0 and tradeable == 0:
        perception_state = "closed_drift"
        notes.append("Broker not fully tradeable; price action may be less actionable.")
    elif avg_abs_pct_change <= 0.05:
        perception_state = "drift_compression"
        notes.append("Very low movement; likely drift/compression.")
    elif avg_abs_pct_change >= 0.25:
        perception_state = "expansion"
        notes.append("Movement expanded; watch for breakout/failure behavior.")
    else:
        perception_state = "mixed"

    quality = 100.0
    if edits_only > 0 and tradeable == 0:
        quality -= 20.0
    if avg_abs_pct_change <= 0.05:
        quality -= 10.0
    if avg_spread is not None and avg_spread >= 8:
        quality -= 15.0

    quality = max(0.0, min(100.0, quality))

    if perception_state == "drift_compression":
        deployment_bias = "cautious"
        size_adjustment = 0.8
        should_reduce = True
        should_block = False
    elif perception_state == "closed_drift":
        deployment_bias = "defensive"
        size_adjustment = 0.7
        should_reduce = True
        should_block = False
    elif perception_state == "expansion":
        deployment_bias = "alert"
        size_adjustment = 1.0
        should_reduce = False
        should_block = False
    else:
        deployment_bias = "neutral"
        size_adjustment = 1.0
        should_reduce = False
        should_block = False

    return {
        "broker_snapshot_ok": live.get("broker_snapshot_ok", False),
        "perception_state": perception_state,
        "avg_abs_pct_change": avg_abs_pct_change,
        "avg_spread": avg_spread,
        "pressure_score": pressure_score,
        "expansion_score": expansion_score,
        "breakout_bias": breakout_bias,
        "directional_pressure": directional_pressure,
        "deployment_bias": deployment_bias,
        "size_adjustment": size_adjustment,
        "should_reduce": should_reduce,
        "should_block": should_block,
        "notes": notes,
    }
