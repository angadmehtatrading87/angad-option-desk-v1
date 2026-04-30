import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.ig_adapter import IGAdapter
from app.ig_session_intelligence import get_ig_session_state

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(BASE_DIR, "data", "ig_cached_snapshot.json")
DXB = ZoneInfo("Asia/Dubai")

def _now():
    return datetime.now(DXB)

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def _load_cache():
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_cache(data):
    with open(CACHE_PATH, "w") as f:
        json.dump(data, f, indent=2)

def _ttl_seconds(session_state=None):
    s = session_state or get_ig_session_state()
    session = s.get("session")
    market_open = bool(s.get("market_open"))
    liquidity = s.get("liquidity")

    if not market_open or session in ("weekend_closed", "friday_close_window"):
        return 600
    if session == "sunday_reopen_probe":
        return 90
    if liquidity == "thin":
        return 90
    if session in ("asia", "asia_friday", "late_us", "friday_reduction"):
        return 45
    if session in ("london", "new_york", "london_friday"):
        return 20
    return 60

def _cache_fresh(cache, ttl):
    ts = cache.get("timestamp")
    if not ts:
        return False
    try:
        dt = datetime.fromisoformat(ts)
    except Exception:
        return False
    return _now() <= dt + timedelta(seconds=ttl)

def get_ig_cached_snapshot(force_refresh=False):
    session_state = get_ig_session_state()
    ttl = _ttl_seconds(session_state)
    cache = _load_cache()

    if (not force_refresh) and cache and _cache_fresh(cache, ttl):
        cache["cache_status"] = "HIT" if cache.get("ok") else "HIT_FAILED_CACHED"
        cache["ttl_seconds"] = ttl
        return cache

    ig = IGAdapter()
    login = ig.login()
    if not login.get("ok"):
        login_body = login.get("body") if isinstance(login.get("body"), dict) else {}
        error_code = str(login_body.get("errorCode") or "")

        if cache and error_code == "error.public-api.exceeded-api-key-allowance":
            reused = dict(cache)
            reused["ok"] = True
            reused["timestamp"] = _now().isoformat()
            reused["cache_status"] = "HIT_LAST_GOOD_ALLOWANCE_FALLBACK"
            reused["session_state"] = session_state
            reused["ttl_seconds"] = ttl
            reused["login"] = login
            return reused

        failed_snapshot = {
            "ok": False,
            "timestamp": _now().isoformat(),
            "cache_status": "MISS_LOGIN_FAILED",
            "session_state": session_state,
            "ttl_seconds": ttl,
            "login": login,
            "positions": {"ok": False, "positions": []},
            "account": {"ok": False}
        }
        _save_cache(failed_snapshot)
        return failed_snapshot
        _save_cache(failed_snapshot)
        return failed_snapshot

    positions_raw = ig.positions()
    watchlist_raw = ig.watchlist_snapshot()
    body = positions_raw.get("body") if isinstance(positions_raw.get("body"), dict) else {}
    rows = body.get("positions", []) if isinstance(body, dict) else []

    cleaned_positions = []
    for row in rows:
        market = row.get("market", {}) or {}
        position = row.get("position", {}) or {}
        cleaned_positions.append({
            "epic": market.get("epic"),
            "name": market.get("instrumentName"),
            "deal_id": position.get("dealId"),
            "deal_reference": position.get("dealReference"),
            "direction": position.get("direction"),
            "size": _safe_float(position.get("size")),
            "level": _safe_float(position.get("level")),
            "stop_level": position.get("stopLevel"),
            "limit_level": position.get("limitLevel"),
            "bid": _safe_float(market.get("bid")),
            "offer": _safe_float(market.get("offer")),
            "percentage_change": _safe_float(market.get("percentageChange")),
            "market_status": market.get("marketStatus"),
        })

    login_body = login.get("body") or {}
    info = login_body.get("accountInfo", {}) or {}
    balance = _safe_float(info.get("balance"))
    open_pnl = _safe_float(info.get("profitLoss"))
    available = _safe_float(info.get("available"))

    snapshot = {
        "ok": True,
        "timestamp": _now().isoformat(),
        "cache_status": "MISS_REFRESHED",
        "ttl_seconds": ttl,
        "session_state": session_state,
        "login": login,
        "account": {
            "ok": True,
            "balance": balance,
            "open_pnl": open_pnl,
            "available": available,
            "equity": balance + open_pnl,
            "account_id": login_body.get("currentAccountId"),
            "currency": login_body.get("currencyIsoCode"),
        },
        "positions": {
            "ok": positions_raw.get("ok", False),
            "positions": cleaned_positions,
            "count": len(cleaned_positions)
        },
        "watchlist": {
            "ok": watchlist_raw.get("ok", False),
            "markets": watchlist_raw.get("markets", [])
        }
    }
    _save_cache(snapshot)
    return snapshot
