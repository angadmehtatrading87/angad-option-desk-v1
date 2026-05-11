import os
from dataclasses import asdict
from typing import Any

from app.market_brain import MarketBrainInput, run_market_brain
from app.market_brain.adapters import IGAdapter as MarketBrainIGAdapter
from app.autonomous_trader_architecture import capital_allocation, validate_market_data


def _env_bool(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, str(default))).strip().lower()
    return raw in ("1", "true", "yes", "on")


def market_brain_execution_config() -> dict[str, Any]:
    mode = str(os.getenv("MARKET_BRAIN_EXECUTION_MODE", "demo")).strip().lower()
    enabled = _env_bool("MARKET_BRAIN_EXECUTION_ENABLED", False)
    mode_allowed = mode in ("demo", "simulation")
    # Thresholds are env-configurable so we can tune them without a redeploy.
    # Demo-phase defaults are intentionally looser than the strict 74/72 we
    # ship as production-grade, so the bot generates trade data we can learn
    # from. Tighten back up before going live with real capital.
    try:
        high_threshold = float(os.getenv("MARKET_BRAIN_HIGH_THRESHOLD", "65.0"))
    except Exception:
        high_threshold = 65.0
    try:
        confidence_threshold = float(os.getenv("MARKET_BRAIN_CONFIDENCE_THRESHOLD", "60.0"))
    except Exception:
        confidence_threshold = 60.0
    try:
        rr_threshold = float(os.getenv("MARKET_BRAIN_RR_THRESHOLD", "1.3"))
    except Exception:
        rr_threshold = 1.3
    return {
        "enabled": enabled,
        "mode": mode,
        "mode_allowed": mode_allowed,
        "blocked_reason": None if mode_allowed else "market_brain_mode_must_be_demo_or_simulation",
        "high_threshold": high_threshold,
        "confidence_threshold": confidence_threshold,
        "rr_threshold": rr_threshold,
    }


def build_market_brain_execution_pick(ig=None, high_threshold: float | None = None, confidence_threshold: float | None = None) -> dict[str, Any]:
    cfg = market_brain_execution_config()
    if not cfg["enabled"]:
        return {"ok": False, "reason": ["market_brain_execution_disabled"], "decisions": [], "skips": [], "bridge": {"config": cfg}}
    if not cfg["mode_allowed"]:
        return {"ok": False, "reason": [cfg["blocked_reason"]], "decisions": [], "skips": [], "bridge": {"config": cfg}}

    # Use env-configurable thresholds unless caller explicitly overrides
    if high_threshold is None:
        high_threshold = cfg["high_threshold"]
    if confidence_threshold is None:
        confidence_threshold = cfg["confidence_threshold"]
    rr_threshold = cfg["rr_threshold"]

    # Fetch the cached IG snapshot. The previous version of this function
    # passed `snapshot=None` which made every call into the adapter blow up
    # with AttributeError on the first attribute access. If no snapshot is
    # available (IG offline / login timing out), bail cleanly here so the
    # worker logs a real reason instead of an exception traceback.
    try:
        from app.ig_api_governor import get_ig_cached_snapshot
        snapshot = get_ig_cached_snapshot(force_refresh=False) or {}
    except Exception as e:
        return {
            "ok": False,
            "reason": [f"snapshot_fetch_error:{type(e).__name__}"],
            "decisions": [],
            "skips": [],
            "bridge": {"config": cfg},
        }

    if not snapshot or snapshot.get("ok") is False:
        return {
            "ok": False,
            "reason": ["snapshot_unavailable"],
            "decisions": [],
            "skips": [],
            "bridge": {"config": cfg, "snapshot_status": snapshot.get("cache_status") if isinstance(snapshot, dict) else None},
        }

    snap_adapter = MarketBrainIGAdapter(snapshot=snapshot)
    watchlist = snap_adapter.get_watchlist() or []
    account = snap_adapter.get_account() or {}
    positions = snap_adapter.get_positions() or []
    candles = snap_adapter.get_candles([m.get("epic") for m in watchlist if isinstance(m, dict) and m.get("epic")]) or {}
    monthly = {"month_start_capital": account.get("balance", 0.0), "trading_days_remaining": 10}
    out = run_market_brain(MarketBrainInput(watchlist=watchlist, candles=candles, account=account, positions=positions, monthly=monthly))

    data_health = validate_market_data({
        "timestamp": account.get("snapshot_time") or account.get("timestamp"),
        "account": account,
        "positions": positions,
        "watchlist": watchlist,
    })
    if not data_health.get("ok"):
        return {"ok": False, "reason": data_health.get("reasons", []), "decisions": [], "skips": [], "bridge": {"config": cfg, "api_health": data_health.get("api_health")}}

    total_cap = float(out.capital.total_capital or 0.0)
    deployable = float(out.capital.deployable_capital or 0.0)
    min_reserve = float(out.capital.min_reserve or 0.0)
    used = float(out.capital.current_used_capital or 0.0)
    reserve_ok = (total_cap - used) >= min_reserve

    disabled_epics = {
        e.strip()
        for e in os.getenv("MARKET_BRAIN_DISABLED_EPICS", "").split(",")
        if e.strip()
    }

    thesis_by_epic = {t.epic: t for t in out.thesis}
    skips = []
    decisions = []

    for opp in out.opportunities:
        if opp.epic in disabled_epics:
            skips.append({
                "epic": opp.epic,
                "reason": "disabled_per_backtest_for_pair",
                "score": opp.opportunity_score,
                "confidence": opp.confidence_score,
                "reject_category": "pair_disabled",
            })
            continue

        reasons = []
        if opp.action != "trade":
            reasons.append("weak_setup_watch_or_reject")
        if float(opp.opportunity_score or 0.0) < high_threshold:
            reasons.append("score_below_high_threshold")
        if float(opp.confidence_score or 0.0) < confidence_threshold:
            reasons.append("confidence_below_threshold")
        if float(opp.rr_ratio or 0.0) < rr_threshold:
            reasons.append("risk_reward_not_acceptable")
        if float(opp.friction_cost_estimate or 0.0) > 0.0025:
            reasons.append("bad_spread_friction")
        if not reserve_ok:
            reasons.append("liquidity_reserve_protection")

        thesis = thesis_by_epic.get(opp.epic)
        thesis_text = ""
        if thesis:
            thesis_text = f"{thesis.why_direction}; {thesis.why_now}; {thesis.structure}".strip()
        if len(thesis_text) < 12:
            reasons.append("missing_trade_thesis")

        recommended_size = float((thesis.recommended_size if thesis else 0.0) or 0.0)
        regime_name = str((opp.regime if hasattr(opp, "regime") else "TREND") or "TREND").upper()
        alloc = capital_allocation(total_cap, used, float(opp.opportunity_score or 0.0), regime_name)
        recommended_size = max(recommended_size, float(alloc.get("recommended_notional", 0.0) or 0.0))
        min_meaningful = max(2500.0, deployable * 0.03)
        is_probe = bool((opp.components or {}).get("probe_trade", False))
        if recommended_size < min_meaningful and not is_probe:
            reasons.append("small_trade_suppressed")

        if reasons:
            skips.append({
                "epic": opp.epic,
                "reason": ",".join(reasons),
                "score": opp.opportunity_score,
                "confidence": opp.confidence_score,
                "reject_category": "bad_regime_or_score" if "score_below_high_threshold" in reasons else "risk_or_friction"
            })
            continue

        action = "WATCH_LONG" if opp.direction == "long" else "WATCH_SHORT"
        conviction_tier = "very_high" if opp.opportunity_score >= 85 and opp.confidence_score >= 82 else "strong"
        allocation_reason = f"tier={conviction_tier}; deployable={deployable:.2f}; suggested_notional={recommended_size:.2f}; objective=4-5pct_monthly"
        decisions.append({
            "epic": opp.epic,
            "name": opp.epic,
            "action": action,
            "reason": f"MarketBrain: {allocation_reason}",
            "confidence": float(opp.confidence_score or 0.0),
            "market_brain": {
                "thesis": thesis_text,
                "score": float(opp.opportunity_score or 0.0),
                "confidence": float(opp.confidence_score or 0.0),
                "rr_ratio": float(opp.rr_ratio or 0.0),
                "friction": float(opp.friction_cost_estimate or 0.0),
                "allocation_reason": allocation_reason,
                "recommended_size": recommended_size,
                "recommended_size_usd": recommended_size,
                "conviction_tier": conviction_tier,
            },
        })

    util = {
        "available_capital": total_cap,
        "deployable_capital": deployable,
        "current_used_capital": used,
        "unused_capital": float(out.capital.unused_capital or 0.0),
        "recommended_utilization": min(0.70, 0.30 + (max([d["market_brain"]["score"] for d in decisions], default=0.0) / 200.0)),
        "actual_utilization": (used / total_cap) if total_cap > 0 else 0.0,
        "under_utilization_reason": "no_high_conviction_candidates" if not decisions else "",
    }

    # Shadow-trade record: log what we WOULD have done at looser thresholds,
    # in parallel to the live decision flow. Best-effort; never blocks live
    # trading.
    try:
        from app.shadow_trade_collector import record_shadow
        record_shadow(
            opportunities=[
                {
                    "epic": o.epic,
                    "direction": o.direction,
                    "opportunity_score": float(o.opportunity_score or 0.0),
                    "confidence_score": float(o.confidence_score or 0.0),
                }
                for o in (out.opportunities or [])
            ],
            live_decisions=decisions,
        )
    except Exception:
        pass

    return {
        "ok": True,
        "reason": [],
        "decisions": decisions,
        "skips": skips,
        "bridge": {
            "config": cfg,
            "capital_utilization": util,
            "market_brain_generated_at": out.generated_at,
            "opportunity_count": len(out.opportunities),
            "rejected_count": len(out.rejected),
            "capital_note": out.capital.recommendation_note,
        },
    }
