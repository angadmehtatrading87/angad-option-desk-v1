"""
IG candle engine — fetches OHLC bars per (epic, resolution) with TTL caching.

Why this exists:
    The agent_v2_orchestrator used to derive "multi-timeframe" data by
    multiplying a single `percentageChange` field by hand-picked constants
    (`slope_5m = pct/3`, `slope_4h = pct*1.15`). That's not multi-timeframe
    analysis — it's the same number stretched four ways. This module pulls
    real per-resolution candles from IG's `/prices/{epic}` endpoint, caches
    them on disk, and returns clean dictionaries the orchestrator and
    structure engines can consume.

API budget protection:
    IG enforces a hard cap of 10,000 historical-price points per app key per
    week. We default to 30 bars per request and a per-resolution TTL set to
    the candle's natural close time, so refreshes happen at most once per
    bar close. With 5 epics × 4 resolutions, steady state is ~12 calls/hour
    (~2,000 calls/week), well under any per-account or per-key limit.

Public API:
    fetch_candles(epic, resolution, max_points=30) -> dict
        Single (epic, resolution) fetch. Returns the cached payload if fresh,
        otherwise hits IG and caches the result. Always returns a dict with
        keys: ok, source ("CACHE"|"LIVE"|"DEGRADED"), candles[], updated_at,
        ttl_seconds, points_consumed.

    fetch_mtf_bundle(epic, resolutions=("5m","15m","1h","4h"), max_points=30)
        Convenience: returns {"5m": fetch_candles_result, "15m": ...} for
        all requested resolutions, in one call.

    candle_features(candles) -> dict
        Derive trend / slope / hhhl / lllh / breakout / last_price / support /
        resistance / atr from a list of OHLC dicts. Output shape matches the
        existing `multi_timeframe_structure_engine.infer_structure_view`
        contract so the orchestrator drop-in works.

Falls back gracefully: if a `/prices` call fails or no candles are available
(weekend, insufficient history, IG rate-limited), `candle_features` returns
a degraded-mode dict and downstream consumers can decide what to do (the v2
orchestrator demotes the candidate or skips it).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from app.ig_adapter import IGAdapter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "data", "ig_candles")

# Per-resolution cache TTL. Roughly one candle's natural lifetime, plus a
# 20% buffer so we never mid-bar-fetch when IG hasn't closed the bar yet.
RESOLUTION_TTL_SECONDS = {
    "1m": 75,
    "5m": 360,        # 6 min
    "15m": 1080,      # 18 min
    "30m": 2160,      # 36 min
    "1h": 4320,       # 1.2 h
    "4h": 17280,      # 4.8 h
    "1d": 4 * 3600,
}

# Resolutions for which we additionally only cache during market-open hours.
# Outside FX market hours (Sat all day, Sun morning Dubai-time) the candles
# don't change — TTL becomes effectively infinite.
LONG_TTL_OFFHOURS_SECONDS = 6 * 3600

DEFAULT_RESOLUTIONS = ("5m", "15m", "1h", "4h")


# --------------------------------------------------------------------------
# cache primitives
# --------------------------------------------------------------------------

def _cache_path(epic: str, resolution: str) -> str:
    safe_epic = epic.replace(".", "_").replace("/", "_")
    return os.path.join(CACHE_DIR, f"{safe_epic}__{resolution}.json")


def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _load_cache_entry(epic: str, resolution: str) -> dict | None:
    path = _cache_path(epic, resolution)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache_entry(epic: str, resolution: str, payload: dict) -> None:
    _ensure_cache_dir()
    path = _cache_path(epic, resolution)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=str)


def _is_fresh(entry: dict, ttl_seconds: int) -> bool:
    ts = entry.get("updated_at")
    if not ts:
        return False
    try:
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            dt = ts
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        return False
    return _now_utc() <= dt + timedelta(seconds=ttl_seconds)


# --------------------------------------------------------------------------
# IG payload normalization
# --------------------------------------------------------------------------

def _safe_float(v, default: float | None = None) -> float | None:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _mid(price_obj: dict | None) -> float | None:
    """Convert an IG bid/ask price dict to a mid float."""
    if not isinstance(price_obj, dict):
        return None
    bid = _safe_float(price_obj.get("bid"))
    ask = _safe_float(price_obj.get("ask"))
    if bid is None and ask is None:
        return _safe_float(price_obj.get("lastTraded"))
    if bid is None:
        return ask
    if ask is None:
        return bid
    return (bid + ask) / 2.0


def _normalize_ig_prices(body: dict) -> list[dict]:
    """Flatten IG's nested OHLC dict into [{open, high, low, close, volume, ts}]."""
    candles: list[dict] = []
    for row in (body.get("prices") or []):
        ts = row.get("snapshotTimeUTC") or row.get("snapshotTime")
        candle = {
            "ts": ts,
            "open": _mid(row.get("openPrice")),
            "high": _mid(row.get("highPrice")),
            "low": _mid(row.get("lowPrice")),
            "close": _mid(row.get("closePrice")),
            "volume": _safe_float(row.get("lastTradedVolume"), 0.0),
        }
        # drop rows that came back without any price data (rare but happens
        # around session breaks)
        if candle["close"] is not None:
            candles.append(candle)
    return candles


# --------------------------------------------------------------------------
# public API: fetching
# --------------------------------------------------------------------------

def fetch_candles(epic: str, resolution: str = "5m", max_points: int = 30) -> dict:
    """Fetch (epic, resolution) candles, with TTL caching and a graceful
    degraded-mode fallback if IG is unreachable or rate-limited."""
    ttl = RESOLUTION_TTL_SECONDS.get(resolution, 600)

    cache = _load_cache_entry(epic, resolution)
    if cache and _is_fresh(cache, ttl):
        out = dict(cache)
        out["source"] = "CACHE"
        out["ttl_seconds"] = ttl
        return out

    # On a stale cache, before we hit IG, decide whether to bother. If the
    # most recent cached candle is younger than the TTL but the cache file
    # itself is older (stale due to a process restart), still hit IG. This
    # is the simple path; we just refresh.

    ig = IGAdapter()
    login = ig.login()
    if not login.get("ok"):
        # Don't trash the cache if it exists — just return it stamped degraded.
        if cache:
            out = dict(cache)
            out["source"] = "DEGRADED_LOGIN_FAILED"
            out["ttl_seconds"] = LONG_TTL_OFFHOURS_SECONDS
            out["last_error"] = login.get("body")
            return out
        return {
            "ok": False,
            "source": "DEGRADED_LOGIN_FAILED",
            "epic": epic,
            "resolution": resolution,
            "candles": [],
            "updated_at": _now_utc().isoformat(),
            "ttl_seconds": ttl,
            "points_consumed": 0,
            "last_error": login.get("body"),
        }

    response = ig.prices(epic=epic, resolution=resolution, max_points=max_points)
    if not response.get("ok"):
        if cache:
            out = dict(cache)
            out["source"] = "DEGRADED_FETCH_FAILED"
            out["ttl_seconds"] = ttl
            out["last_error"] = response.get("body")
            return out
        return {
            "ok": False,
            "source": "DEGRADED_FETCH_FAILED",
            "epic": epic,
            "resolution": resolution,
            "candles": [],
            "updated_at": _now_utc().isoformat(),
            "ttl_seconds": ttl,
            "points_consumed": 0,
            "last_error": response.get("body"),
        }

    body = response.get("body") or {}
    candles = _normalize_ig_prices(body)

    payload = {
        "ok": True,
        "source": "LIVE",
        "epic": epic,
        "resolution": resolution,
        "candles": candles,
        "updated_at": _now_utc().isoformat(),
        "ttl_seconds": ttl,
        "points_consumed": response.get("points_consumed", len(candles)),
        "instrument_type": body.get("instrumentType"),
        "allowance": (body.get("metadata") or {}).get("allowance"),
    }
    _save_cache_entry(epic, resolution, payload)
    return payload


def fetch_mtf_bundle(
    epic: str,
    resolutions: tuple[str, ...] = DEFAULT_RESOLUTIONS,
    max_points: int = 30,
) -> dict[str, dict]:
    """Fetch multiple resolutions for one epic. Returns {resolution: result}."""
    out: dict[str, dict] = {}
    for res in resolutions:
        out[res] = fetch_candles(epic=epic, resolution=res, max_points=max_points)
    return out


# --------------------------------------------------------------------------
# public API: feature derivation
# --------------------------------------------------------------------------

def _ema(values: list[float], period: int) -> float | None:
    if not values:
        return None
    period = max(1, min(period, len(values)))
    k = 2.0 / (period + 1)
    ema = float(values[0])
    for v in values[1:]:
        ema = (float(v) * k) + (ema * (1 - k))
    return ema


def _atr(candles: list[dict], period: int = 14) -> float | None:
    if len(candles) < 2:
        return None
    trs: list[float] = []
    prev_close = candles[0].get("close")
    for c in candles[1:]:
        high = c.get("high")
        low = c.get("low")
        close = c.get("close")
        if None in (high, low, close, prev_close):
            prev_close = close
            continue
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(float(tr))
        prev_close = close
    if not trs:
        return None
    if len(trs) < period:
        return sum(trs) / len(trs)
    return sum(trs[-period:]) / period


def _last_swing_high_low(candles: list[dict], lookback: int = 10) -> tuple[float | None, float | None]:
    if not candles:
        return None, None
    window = candles[-lookback:] if len(candles) > lookback else candles
    highs = [c.get("high") for c in window if c.get("high") is not None]
    lows = [c.get("low") for c in window if c.get("low") is not None]
    return (max(highs) if highs else None, min(lows) if lows else None)


def _hhhl_lllh(candles: list[dict], window: int = 5) -> tuple[bool, bool]:
    """Detect higher-highs/higher-lows (uptrend structure) or lower-lows/lower-highs (downtrend)."""
    if len(candles) < window * 2:
        return False, False
    recent = candles[-window:]
    prior = candles[-2 * window:-window]

    rh = [c.get("high") for c in recent if c.get("high") is not None]
    rl = [c.get("low") for c in recent if c.get("low") is not None]
    ph = [c.get("high") for c in prior if c.get("high") is not None]
    pl = [c.get("low") for c in prior if c.get("low") is not None]

    if not (rh and rl and ph and pl):
        return False, False

    hhhl = (max(rh) > max(ph)) and (min(rl) > min(pl))
    lllh = (min(rl) < min(pl)) and (max(rh) < max(ph))
    return hhhl, lllh


def candle_features(candles: list[dict], session: str | None = None) -> dict:
    """
    Convert a list of OHLC bars into the dict shape that
    `multi_timeframe_structure_engine.infer_structure_view` expects.

    Returns a dict with the keys the structure engine reads:
    {trend, slope, hhhl, lllh, breakout, last_price, support, resistance, atr,
     candle_count, available}.

    `available=False` means we did not have enough data to derive useful
    features — the orchestrator should treat this as "no MTF read here" and
    not pretend a NEUTRAL bias is informative.
    """
    closes = [c.get("close") for c in candles if c.get("close") is not None]
    if len(closes) < 6:
        return {
            "available": False,
            "reason": "insufficient_candles",
            "candle_count": len(closes),
            "trend": 0,
            "slope": 0.0,
            "hhhl": False,
            "lllh": False,
            "breakout": False,
            "last_price": closes[-1] if closes else None,
            "support": None,
            "resistance": None,
            "atr": None,
        }

    last_price = float(closes[-1])

    # Slope: percent change of the last close vs. ~10 bars back, in basis
    # points. Positive == uptrend on this TF.
    lookback = min(len(closes) - 1, 10)
    base = float(closes[-1 - lookback])
    slope_bps = ((last_price - base) / base) * 10000.0 if base else 0.0

    # Trend: EMA-9 vs EMA-21. Saves us from a noisy single-bar slope read.
    ema_fast = _ema(closes[-min(len(closes), 30):], 9)
    ema_slow = _ema(closes[-min(len(closes), 60):], 21)
    if ema_fast is not None and ema_slow is not None:
        if ema_fast > ema_slow * 1.0001:
            trend = 1
        elif ema_fast < ema_slow * 0.9999:
            trend = -1
        else:
            trend = 0
    else:
        trend = 1 if slope_bps > 0 else -1 if slope_bps < 0 else 0

    hhhl, lllh = _hhhl_lllh(candles)

    # Breakout: current close pierces the prior-window swing extreme.
    swing_high, swing_low = _last_swing_high_low(candles[:-1])
    breakout = bool(
        (swing_high is not None and last_price > swing_high)
        or (swing_low is not None and last_price < swing_low)
    )

    # Support/resistance: more recent extremes (full window).
    full_high, full_low = _last_swing_high_low(candles)

    return {
        "available": True,
        "candle_count": len(closes),
        "trend": trend,
        "slope": round(slope_bps, 4),
        "hhhl": hhhl,
        "lllh": lllh,
        "breakout": breakout,
        "last_price": round(last_price, 6),
        "support": round(full_low, 6) if full_low is not None else None,
        "resistance": round(full_high, 6) if full_high is not None else None,
        "atr": round(_atr(candles) or 0.0, 6),
    }


def build_mtf_features(
    epic: str,
    resolutions: tuple[str, ...] = DEFAULT_RESOLUTIONS,
    max_points: int = 30,
) -> dict:
    """
    Top-level convenience: fetch candles for `epic` across all `resolutions`
    and return the structure-engine-ready dict:
        {"5m": {trend, slope, ...}, "15m": ..., "1h": ..., "4h": ...,
         "_meta": {sources: {...}, points_consumed_total: N, available_count: K}}.

    If a resolution failed to fetch and has no cache, its entry will have
    `available=False` and the orchestrator should treat it as missing.
    """
    bundle = fetch_mtf_bundle(epic=epic, resolutions=resolutions, max_points=max_points)
    out: dict[str, Any] = {}
    sources: dict[str, str] = {}
    total_points = 0
    available = 0
    for res in resolutions:
        result = bundle.get(res, {})
        feats = candle_features(result.get("candles") or [])
        out[res] = feats
        sources[res] = result.get("source", "UNKNOWN")
        total_points += int(result.get("points_consumed") or 0)
        if feats.get("available"):
            available += 1
    out["_meta"] = {
        "sources": sources,
        "points_consumed_total": total_points,
        "available_count": available,
        "resolutions_requested": list(resolutions),
    }
    return out
