import os
from dataclasses import asdict
from typing import Any

from app.market_brain import MarketBrainInput, run_market_brain
from app.market_brain.adapters import IGAdapter as MarketBrainIGAdapter


def _env_bool(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, str(default))).strip().lower()
    return raw in ("1", "true", "yes", "on")


def market_brain_execution_config() -> dict[str, Any]:
    mode = str(os.getenv("MARKET_BRAIN_EXECUTION_MODE", "demo")).strip().lower()
    enabled = _env_bool("MARKET_BRAIN_EXECUTION_ENABLED", False)
    mode_allowed = mode in ("demo", "simulation")
    return {
        "enabled": enabled,
        "mode": mode,
        "mode_allowed": mode_allowed,
        "blocked_reason": None if mode_allowed else "market_brain_mode_must_be_demo_or_simulation",
    }


def build_market_brain_execution_pick(ig=None, high_threshold: float = 74.0, confidence_threshold: float = 72.0) -> dict[str, Any]:
    cfg = market_brain_execution_config()
    if not cfg["enabled"]:
        return {"ok": False, "reason": ["market_brain_execution_disabled"], "decisions": [], "skips": [], "bridge": {"config": cfg}}
    if not cfg["mode_allowed"]:
        return {"ok": False, "reason": [cfg["blocked_reason"]], "decisions": [], "skips": [], "bridge": {"config": cfg}}

    snap_adapter = MarketBrainIGAdapter(snapshot=None)
    watchlist = snap_adapter.get_watchlist()
    account = snap_adapter.get_account()
    positions = snap_adapter.get_positions()
    candles = snap_adapter.get_candles([m.get("epic") for m in watchlist if m.get("epic")])
    monthly = {"month_start_capital": account.get("balance", 0.0), "trading_days_remaining": 10}
    out = run_market_brain(MarketBrainInput(watchlist=watchlist, candles=candles, account=account, positions=positions, monthly=monthly))

    total_cap = float(out.capital.total_capital or 0.0)
    deployable = float(out.capital.deployable_capital or 0.0)
    min_reserve = float(out.capital.min_reserve or 0.0)
    used = float(out.capital.current_used_capital or 0.0)
    reserve_ok = (total_cap - used) >= min_reserve

    thesis_by_epic = {t.epic: t for t in out.thesis}
    skips = []
    decisions = []

    for opp in out.opportunities:
        reasons = []
        if opp.action != "trade":
            reasons.append("weak_setup_watch_or_reject")
        if float(opp.opportunity_score or 0.0) < high_threshold:
            reasons.append("score_below_high_threshold")
        if float(opp.confidence_score or 0.0) < confidence_threshold:
            reasons.append("confidence_below_threshold")
        if float(opp.rr_ratio or 0.0) < 1.5:
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
        min_meaningful = max(2500.0, deployable * 0.03)
        is_probe = bool((opp.components or {}).get("probe_trade", False))
        if recommended_size < min_meaningful and not is_probe:
            reasons.append("small_trade_suppressed")

        if reasons:
            skips.append({"epic": opp.epic, "reason": ",".join(reasons), "score": opp.opportunity_score, "confidence": opp.confidence_score})
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
