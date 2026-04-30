from app.ig_api_governor import get_ig_cached_snapshot
from app.ig_adapter import IGAdapter
from app.ig_live_book_memory import save_last_good_live_book, get_last_good_live_book

def _normalize_cached_rows(rows):
    out = []
    for r in rows or []:
        out.append({
            "epic": r.get("epic"),
            "name": r.get("name"),
            "deal_id": r.get("deal_id"),
            "deal_reference": r.get("deal_reference"),
            "direction": r.get("direction"),
            "size": r.get("size"),
            "level": r.get("level"),
            "stop_level": r.get("stop_level"),
            "limit_level": r.get("limit_level"),
            "bid": r.get("bid"),
            "offer": r.get("offer"),
            "percentage_change": r.get("percentage_change"),
            "market_status": r.get("market_status"),
        })
    return out

def _normalize_live_payload(raw):
    out = []
    for item in raw or []:
        position = item.get("position", {}) or {}
        market = item.get("market", {}) or {}
        out.append({
            "epic": market.get("epic"),
            "name": market.get("instrumentName"),
            "deal_id": position.get("dealId"),
            "deal_reference": position.get("dealReference"),
            "direction": position.get("direction"),
            "size": position.get("size"),
            "level": position.get("level"),
            "stop_level": position.get("stopLevel"),
            "limit_level": position.get("limitLevel"),
            "bid": market.get("bid"),
            "offer": market.get("offer"),
            "percentage_change": market.get("percentageChange"),
            "market_status": market.get("marketStatus"),
        })
    return out

def get_unified_live_rows():
    snap = get_ig_cached_snapshot()
    cached_rows = _normalize_cached_rows(((snap.get("positions") or {}).get("positions") or []))
    if cached_rows:
        payload = {
            "ok": True,
            "source": "cached_snapshot",
            "broker_snapshot_ok": bool(snap.get("ok", False)),
            "rows": cached_rows,
            "login": snap.get("login"),
            "account": snap.get("account"),
        }
        save_last_good_live_book(payload)
        return payload

    try:
        ig = IGAdapter()
        login = ig.login()
        if not login.get("ok"):
            fallback = get_last_good_live_book()
            if fallback:
                return {
                    **fallback,
                    "ok": True,
                    "source": "last_good_fallback_after_login_failure",
                    "broker_snapshot_ok": False,
                    "fallback_used": True,
                    "login": login,
                }
            return {
                "ok": False,
                "source": "live_login_failed",
                "broker_snapshot_ok": False,
                "rows": [],
                "login": login,
                "account": {"ok": False},
            }

        pos = ig.fetch_positions()
        body = pos.get("body") if isinstance(pos.get("body"), dict) else {}
        raw = body.get("positions", []) if isinstance(body, dict) else []
        live_rows = _normalize_live_payload(raw)

        payload = {
            "ok": bool(live_rows),
            "source": "live_broker_fetch",
            "broker_snapshot_ok": True,
            "rows": live_rows,
            "login": login,
            "account": {
                "ok": True,
                "account_id": ig.account_id,
            },
        }
        if live_rows:
            save_last_good_live_book(payload)
        return payload
    except Exception as e:
        fallback = get_last_good_live_book()
        if fallback:
            return {
                **fallback,
                "ok": True,
                "source": "last_good_fallback_after_exception",
                "broker_snapshot_ok": False,
                "fallback_used": True,
                "error": str(e),
            }
        return {
            "ok": False,
            "source": "live_exception",
            "broker_snapshot_ok": False,
            "rows": [],
            "error": str(e),
            "account": {"ok": False},
        }
