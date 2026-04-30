from app.ig_adapter import IGAdapter

def get_live_ig_positions():
    ig = IGAdapter()
    login = ig.login()
    if not login.get("ok"):
        return {"ok": False, "reason": "login_failed", "positions": []}

    pos = ig.positions()
    if not pos.get("ok"):
        return {"ok": False, "reason": "positions_failed", "positions": []}

    body = pos.get("body") if isinstance(pos.get("body"), dict) else {}
    positions = body.get("positions", []) if isinstance(body, dict) else []

    normalized = []
    for row in positions:
        market = row.get("market", {}) or {}
        position = row.get("position", {}) or {}

        normalized.append({
            "epic": market.get("epic"),
            "name": market.get("instrumentName"),
            "direction": position.get("direction"),
            "size": position.get("size"),
            "deal_id": position.get("dealId"),
            "deal_reference": position.get("dealReference"),
            "entry_level": position.get("level"),
            "stop_level": position.get("stopLevel"),
            "limit_level": position.get("limitLevel"),
            "bid": market.get("bid"),
            "offer": market.get("offer"),
            "percentage_change": market.get("percentageChange"),
            "market_status": market.get("marketStatus")
        })

    return {"ok": True, "positions": normalized}
