from app.tasty_connector import get_market_data

def safe_float(value, default=None):
    try:
        return float(value)
    except Exception:
        return default

def quote_options(option_symbols):
    resp = get_market_data("Equity Option", option_symbols)

    if resp["status_code"] != 200:
        raise RuntimeError(f"Quote fetch failed: {resp}")

    items = resp["body"].get("data", {}).get("items", [])

    quotes = {}
    for item in items:
        symbol = item.get("symbol")
        quotes[symbol] = {
            "symbol": symbol,
            "bid": safe_float(item.get("bid")),
            "ask": safe_float(item.get("ask")),
            "mid": safe_float(item.get("mid")),
            "mark": safe_float(item.get("mark")),
            "last": safe_float(item.get("last")),
            "volume": safe_float(item.get("volume"), 0),
            "open_interest": safe_float(item.get("open-interest"), 0),
            "delta": safe_float(item.get("delta")),
            "gamma": safe_float(item.get("gamma")),
            "theta": safe_float(item.get("theta")),
            "vega": safe_float(item.get("vega")),
            "volatility": safe_float(item.get("volatility")),
            "updated_at": item.get("updated-at"),
        }

    return quotes

def quote_quality(q):
    if not q:
        return {
            "ok": False,
            "reason": "Missing quote.",
            "score": 0
        }

    bid = q.get("bid")
    ask = q.get("ask")
    volume = q.get("volume") or 0
    oi = q.get("open_interest") or 0

    if bid is None or ask is None:
        return {
            "ok": False,
            "reason": "Missing bid/ask.",
            "score": 0
        }

    if bid <= 0 or ask <= 0:
        return {
            "ok": False,
            "reason": "Bid/ask is zero or invalid.",
            "score": 0
        }

    spread = ask - bid
    mid = (ask + bid) / 2

    spread_pct = spread / mid if mid > 0 else 999

    if spread_pct > 0.20:
        return {
            "ok": False,
            "reason": f"Bid/ask spread too wide: {round(spread_pct * 100, 2)}%.",
            "score": 0
        }

    score = 50

    if spread_pct <= 0.03:
        score += 25
    elif spread_pct <= 0.07:
        score += 15
    elif spread_pct <= 0.12:
        score += 8

    if oi >= 1000:
        score += 15
    elif oi >= 250:
        score += 10
    elif oi >= 50:
        score += 5

    if volume >= 500:
        score += 10
    elif volume >= 50:
        score += 5
    elif volume >= 1:
        score += 2

    return {
        "ok": True,
        "reason": "Quote quality acceptable.",
        "spread_pct": round(spread_pct * 100, 2),
        "volume": volume,
        "open_interest": oi,
        "score": min(score, 100)
    }
