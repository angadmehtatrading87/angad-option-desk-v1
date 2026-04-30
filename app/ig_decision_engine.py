from app.ig_state import get_ig_state

LONG_TRIGGER = 0.03
SHORT_TRIGGER = -0.03

def infer_ig_signal(market_body):
    snap = (market_body or {}).get("snapshot", {})
    inst = (market_body or {}).get("instrument", {})

    change = snap.get("percentageChange")
    status = snap.get("marketStatus")
    market_name = inst.get("name")
    epic = inst.get("epic")

    if status != "TRADEABLE":
        return {
            "epic": epic,
            "name": market_name,
            "action": "NO_TRADE",
            "reason": f"Market status {status}",
            "confidence": 0
        }

    if change is None:
        return {
            "epic": epic,
            "name": market_name,
            "action": "NO_TRADE",
            "reason": "Missing percentage change",
            "confidence": 0
        }

    change = float(change)

    if change >= LONG_TRIGGER:
        conf = min(85, 55 + abs(change) * 200)
        return {
            "epic": epic,
            "name": market_name,
            "action": "WATCH_LONG",
            "reason": f"Positive short-term momentum ({change}%)",
            "confidence": round(conf, 1)
        }

    if change <= SHORT_TRIGGER:
        conf = min(85, 55 + abs(change) * 200)
        return {
            "epic": epic,
            "name": market_name,
            "action": "WATCH_SHORT",
            "reason": f"Negative short-term momentum ({change}%)",
            "confidence": round(conf, 1)
        }

    return {
        "epic": epic,
        "name": market_name,
        "action": "NO_TRADE",
        "reason": f"Move too small ({change}%)",
        "confidence": 20
    }

def build_ig_decisions():
    state = get_ig_state()
    watchlist = state.get("watchlist") or {}
    markets = watchlist.get("markets") or []

    decisions = []
    for row in markets:
        snap = row.get("snapshot") or {}
        if not snap.get("ok"):
            decisions.append({
                "epic": row.get("epic"),
                "name": row.get("epic"),
                "action": "NO_TRADE",
                "reason": "Market lookup failed",
                "confidence": 0
            })
            continue
        body = snap.get("body") or {}
        decisions.append(infer_ig_signal(body))

    return {
        "state": state,
        "decisions": decisions
    }
