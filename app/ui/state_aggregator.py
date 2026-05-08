"""
Live UI state aggregator.

Collects everything the dashboard needs in one cheap function call. All
sub-fetches are wrapped in try/except so a single broken upstream doesn't
take the dashboard offline.

Returns a JSON-serializable dict:
    {
      "ts": "2026-05-06T16:00:00+04:00",
      "account":   {equity, available, open_pnl, balance, account_id},
      "positions": [...],
      "regime":    {regime, quality_score, ...},
      "deployment":{mode, target_pct, floor_pct, ...},
      "candidates": [ ... 0..N high-conviction setups ... ],
      "ranked":     [ ... all scored pairs ... ],
      "mtf_diagnostics": { epic: {degraded, sources, ...} },
      "cost_cap":  {rows, kill_switches, alerts_sent},
      "shadow":    {records, by_tier, window_hours},
      "session":   "Asia"|"London"|"New York"|"Late NY",
      "kill":      {trading_killed, llm_calls_killed},
      "errors":    [...]   # any sub-fetch failures, for debug
    }

The result is cached in-process for `_CACHE_TTL_SECONDS` seconds so that
the dashboard's 5-second polling only triggers 1 real computation per 30
seconds. Without this cache, every browser-tab open hammers IG with
multi-timeframe candle fetches every 5 seconds (which blew through 95% of
our daily IG API budget on 2026-05-07).
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

DXB = ZoneInfo("Asia/Dubai")

# Module-level cache for aggregate_live_state. Thread-safe.
_CACHE_LOCK = threading.Lock()
_CACHE: dict = {"data": None, "expires_at": 0.0}
_CACHE_TTL_SECONDS = 30.0


def _safe(fn, default, errors: list, label: str):
    try:
        return fn()
    except Exception as e:
        errors.append(f"{label}: {type(e).__name__}: {e}")
        return default


def _session_label(now: datetime) -> str:
    h = now.hour
    if 3 <= h < 11:
        return "Asia"
    if 11 <= h < 17:
        return "London"
    if 17 <= h < 23:
        return "New York"
    return "Late NY / Asia open"


def aggregate_live_state(force_refresh: bool = False) -> dict:
    """Returns the cached state if it's fresh (<30s old), otherwise rebuilds.

    Pass `force_refresh=True` to bypass the cache (for testing). The cache
    is shared across requests, so when 5 dashboards poll within 30s they
    all get the same payload but only one actually hits IG.
    """
    if not force_refresh:
        with _CACHE_LOCK:
            cached = _CACHE.get("data")
            expires_at = _CACHE.get("expires_at", 0.0)
            if cached is not None and time.monotonic() < expires_at:
                # Return a shallow copy stamped with cache_age so the caller
                # can see how stale this is. Don't mutate the cached object.
                age = round(_CACHE_TTL_SECONDS - (expires_at - time.monotonic()), 1)
                copy = dict(cached)
                copy["_cache"] = {"hit": True, "age_seconds": age, "ttl": _CACHE_TTL_SECONDS}
                return copy

    return _aggregate_live_state_uncached()


def _aggregate_live_state_uncached() -> dict:
    errors: list[str] = []
    now = datetime.now(DXB)

    plan = _safe(
        lambda: __import__("app.agent_v2_orchestrator", fromlist=["build_agent_v2_plan"]).build_agent_v2_plan() or {},
        default={},
        errors=errors, label="v2_plan",
    )

    ig_snap = _safe(
        lambda: __import__("app.ig_api_governor", fromlist=["get_ig_cached_snapshot"]).get_ig_cached_snapshot(force_refresh=False) or {},
        default={},
        errors=errors, label="ig_snapshot",
    )

    cost = _safe(
        lambda: __import__("app.cost_cap_meter", fromlist=["snapshot"]).snapshot(),
        default={"rows": [], "kill_switches": {}},
        errors=errors, label="cost_cap",
    )

    shadow = _safe(
        lambda: __import__("app.shadow_trade_collector", fromlist=["summarize_window"]).summarize_window(hours=24),
        default={"records": 0, "by_tier": {}},
        errors=errors, label="shadow",
    )

    account = (plan.get("account") or ig_snap.get("account") or {}) if isinstance(plan, dict) else {}
    positions = ((ig_snap.get("positions") or {}).get("positions") or []) if isinstance(ig_snap, dict) else []

    result = {
        "ts": now.isoformat(),
        "session": _session_label(now),
        "account": {
            "equity": account.get("equity"),
            "available": account.get("available"),
            "open_pnl": account.get("open_pnl"),
            "balance": account.get("balance"),
            "account_id": account.get("account_id"),
        },
        "positions": positions,
        "regime": (plan.get("regime") or {}) if isinstance(plan, dict) else {},
        "deployment": (plan.get("deployment") or {}) if isinstance(plan, dict) else {},
        "loss_governor": (plan.get("loss_governor") or {}) if isinstance(plan, dict) else {},
        "book_directive": (plan.get("book_directive") or {}) if isinstance(plan, dict) else {},
        "candidates": (plan.get("candidates") or []) if isinstance(plan, dict) else [],
        "ranked": (plan.get("ranked") or []) if isinstance(plan, dict) else [],
        "mtf_diagnostics": (plan.get("mtf_diagnostics") or {}) if isinstance(plan, dict) else {},
        "cost_cap": cost,
        "shadow": shadow,
        "kill_switches": cost.get("kill_switches") if isinstance(cost, dict) else {},
        "errors": errors,
        "_cache": {"hit": False, "age_seconds": 0.0, "ttl": _CACHE_TTL_SECONDS},
    }

    # Update cache. Don't include the _cache marker in the cached payload
    # itself — the read path stamps that fresh on each cache hit.
    cacheable = dict(result)
    cacheable.pop("_cache", None)
    with _CACHE_LOCK:
        _CACHE["data"] = cacheable
        _CACHE["expires_at"] = time.monotonic() + _CACHE_TTL_SECONDS

    return result
