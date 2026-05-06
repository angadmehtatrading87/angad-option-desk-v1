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
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

DXB = ZoneInfo("Asia/Dubai")


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


def aggregate_live_state() -> dict:
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

    return {
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
    }
