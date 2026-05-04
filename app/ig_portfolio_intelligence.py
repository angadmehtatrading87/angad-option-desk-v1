from app.ig_live_book_source import get_unified_live_rows

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def _extract_ccy_pair(epic, name):
    text = f"{epic or ''} {name or ''}".upper()
    pairs = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "USDCHF", "AUDUSD", "NZDUSD", "EURJPY", "GBPJPY"]
    for p in pairs:
        if p in text:
            return p[:3], p[3:]
    return None, None

def _side_exposure(direction, base, quote, size):
    # BUY base/quote => long base, short quote
    # SELL base/quote => short base, long quote
    out = {}
    if not base or not quote:
        return out
    s = _safe_float(size, 0.0)
    if s <= 0:
        return out
    if str(direction).upper() == "BUY":
        out[base] = out.get(base, 0.0) + s
        out[quote] = out.get(quote, 0.0) - s
    else:
        out[base] = out.get(base, 0.0) - s
        out[quote] = out.get(quote, 0.0) + s
    return out

def build_portfolio_intelligence():
    live = get_unified_live_rows()
    rows = live.get("rows", [])

    currency_exposure = {}
    directional_clusters = {}
    symbol_counts = {}
    total_positions = len(rows)
    total_size = 0.0

    for r in rows:
        epic = r.get("epic")
        name = r.get("name")
        direction = str(r.get("direction") or "").upper()
        size = _safe_float(r.get("size"), 0.0)
        total_size += size

        symbol_counts[epic] = symbol_counts.get(epic, 0) + 1
        directional_clusters[(epic, direction)] = directional_clusters.get((epic, direction), 0) + size

        base, quote = _extract_ccy_pair(epic, name)
        for ccy, amt in _side_exposure(direction, base, quote, size).items():
            currency_exposure[ccy] = currency_exposure.get(ccy, 0.0) + amt

    biggest_abs_ccy = 0.0
    largest_ccy = None
    for ccy, amt in currency_exposure.items():
        if abs(amt) > biggest_abs_ccy:
            biggest_abs_ccy = abs(amt)
            largest_ccy = ccy

    duplicate_symbols = [k for k, v in symbol_counts.items() if v >= 2]
    heavy_directionals = [
        {"epic": k[0], "direction": k[1], "size": round(v, 2)}
        for k, v in directional_clusters.items()
        if v >= 4
    ]
    heavy_directionals.sort(key=lambda x: x["size"], reverse=True)

    fragility_score = 0.0
    notes = []

    if duplicate_symbols:
        fragility_score += min(20.0, len(duplicate_symbols) * 4.0)
        notes.append("Duplicate symbol concentration detected.")

    if heavy_directionals:
        fragility_score += min(30.0, len(heavy_directionals) * 5.0)
        notes.append("Same-direction clustering detected.")

    if biggest_abs_ccy >= 8:
        fragility_score += 25.0
        notes.append(f"Large single-currency exposure detected in {largest_ccy}.")
    elif biggest_abs_ccy >= 4:
        fragility_score += 12.0
        notes.append(f"Moderate currency concentration detected in {largest_ccy}.")

    if total_positions >= 8:
        fragility_score += 15.0
        notes.append("Book is carrying many open positions.")
    elif total_positions >= 5:
        fragility_score += 8.0
        notes.append("Book has moderate position count.")

    fragility_score = round(min(100.0, fragility_score), 2)

    if fragility_score >= 55:
        deployment_bias = "defensive"
        size_adjustment = 0.55
        should_reduce = True
        should_block_new = False
    elif fragility_score >= 35:
        deployment_bias = "cautious"
        size_adjustment = 0.75
        should_reduce = True
        should_block_new = False
    else:
        deployment_bias = "neutral"
        size_adjustment = 1.0
        should_reduce = False
        should_block_new = False

    block_rule = ""
    block_reason = ""
    is_overly_conservative = False

    if total_positions >= 10:
        should_block_new = True
        deployment_bias = "book_full"
        size_adjustment = 0.0
        notes.append("Book too full; block new deployment.")
        block_rule = "max_open_positions"
        block_reason = "open_positions_gte_10"
    elif not live.get("broker_snapshot_ok", False):
        should_block_new = True
        deployment_bias = "book_state_uncertain"
        size_adjustment = min(size_adjustment, 0.5)
        notes.append("Broker snapshot stale/unavailable; block new deployment.")
        block_rule = "stale_portfolio_state"
        block_reason = "broker_snapshot_not_ok"
        is_overly_conservative = True

    return {
        "broker_snapshot_ok": bool(live.get("broker_snapshot_ok", False)),
        "total_positions": total_positions,
        "total_size": round(total_size, 2),
        "currency_exposure": {k: round(v, 2) for k, v in currency_exposure.items()},
        "largest_currency_exposure": {
            "currency": largest_ccy,
            "abs_size": round(biggest_abs_ccy, 2),
        },
        "duplicate_symbols": duplicate_symbols,
        "heavy_directionals": heavy_directionals,
        "fragility_score": fragility_score,
        "deployment_bias": deployment_bias,
        "size_adjustment": size_adjustment,
        "should_reduce": should_reduce,
        "should_block_new": should_block_new,
        "block_rule": block_rule,
        "block_reason": block_reason,
        "is_overly_conservative": bool(is_overly_conservative),
        "notes": notes,
        "source": live.get("source"),
    }
