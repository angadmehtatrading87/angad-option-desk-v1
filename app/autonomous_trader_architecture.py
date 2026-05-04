from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


REGIME_MULTIPLIER = {
    "TREND": 1.0,
    "RANGE": 0.7,
    "CHOP": 0.2,
    "HIGH_VOL": 0.5,
    "LOW_VOL": 0.6,
    "NEWS_DRIVEN": 0.35,
    "GAP_DRIVEN": 0.4,
    "NO_TRADE": 0.0,
}


def _sf(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d


@dataclass
class Candidate:
    epic: str
    direction: str
    spread_bps: float
    momentum: float
    trend: float
    structure: float
    volatility: float
    rr: float
    confidence: float


def detect_regime(candles: list[dict[str, Any]] | None) -> dict[str, Any]:
    candles = candles or []
    if len(candles) < 20:
        return {"regime": "NO_TRADE", "confidence": 25.0, "reason": "insufficient_candles"}
    closes = [_sf(c.get("close")) for c in candles if c.get("close") is not None]
    if len(closes) < 20:
        return {"regime": "NO_TRADE", "confidence": 30.0, "reason": "bad_candle_quality"}
    drift = closes[-1] - closes[-20]
    chg = [abs(closes[i] - closes[i - 1]) for i in range(1, len(closes))]
    mean_move = (sum(chg) / len(chg)) if chg else 0.0
    if mean_move <= 0:
        return {"regime": "NO_TRADE", "confidence": 20.0, "reason": "flat_tape"}
    ratio = abs(drift) / max(mean_move * 10.0, 1e-9)
    if ratio > 1.1:
        return {"regime": "TREND", "confidence": min(95.0, 60 + ratio * 15), "reason": "persistent_direction"}
    if ratio < 0.3:
        return {"regime": "CHOP", "confidence": min(90.0, 55 + (0.3 - ratio) * 80), "reason": "directionless_noise"}
    return {"regime": "RANGE", "confidence": 62.0, "reason": "bounded_rotation"}


def score_candidate(c: Candidate, regime: dict[str, Any], news_state: dict[str, Any] | None = None) -> dict[str, Any]:
    news_state = news_state or {"available": False, "bias": "neutral"}
    news_score = 55.0 if news_state.get("available") else 45.0
    spread_score = max(0.0, min(100.0, 100.0 - (c.spread_bps * 8.0)))
    momentum_score = max(0.0, min(100.0, c.momentum))
    trend_score = max(0.0, min(100.0, c.trend))
    structure_score = max(0.0, min(100.0, c.structure))
    vol_score = max(0.0, min(100.0, c.volatility))
    rr_score = max(0.0, min(100.0, c.rr * 30.0))
    regime_score = max(0.0, min(100.0, _sf(regime.get("confidence"), 40.0)))

    final = (
        trend_score * 0.14 + momentum_score * 0.13 + structure_score * 0.12 + regime_score * 0.14
        + vol_score * 0.08 + spread_score * 0.11 + news_score * 0.05 + rr_score * 0.13 + c.confidence * 0.10
    )
    return {
        "tradability_score": round(final, 2),
        "components": {
            "trend": trend_score, "momentum": momentum_score, "structure": structure_score,
            "regime": regime_score, "volatility": vol_score, "friction": spread_score,
            "news_macro": news_score, "risk_reward": rr_score, "confidence": c.confidence,
        },
        "why": {
            "instrument": f"{c.epic} selected for liquidity/spread profile",
            "direction": f"{c.direction} aligned to trend/momentum",
            "why_now": f"regime={regime.get('regime')} confidence={regime.get('confidence')}",
        },
    }


def capital_allocation(total_equity: float, used_capital: float, score: float, regime_name: str, drawdown: float = 0.0) -> dict[str, Any]:
    reserve = total_equity * 0.30
    available = max(total_equity - used_capital, 0.0)
    deployable = max(0.0, available - reserve)
    conviction = max(0.0, min(1.0, (score - 55.0) / 45.0))
    regime_mult = REGIME_MULTIPLIER.get(regime_name, 0.5)
    drawdown_mult = max(0.25, 1.0 - max(0.0, drawdown))
    recommended = deployable * conviction * regime_mult * drawdown_mult
    min_useful = max(1000.0, total_equity * 0.01)
    under_utilized = deployable > (total_equity * 0.15) and recommended < min_useful
    return {
        "total_equity": round(total_equity, 2),
        "used_capital": round(used_capital, 2),
        "available_capital": round(available, 2),
        "deployable_capital": round(deployable, 2),
        "liquidity_reserve": round(reserve, 2),
        "recommended_notional": round(max(0.0, recommended), 2),
        "minimum_useful_trade_size": round(min_useful, 2),
        "under_utilization_detected": under_utilized,
        "allocation_reason": f"conviction={conviction:.2f}, regime_mult={regime_mult:.2f}, drawdown_mult={drawdown_mult:.2f}",
    }


def validate_market_data(snapshot: dict[str, Any] | None, max_age_seconds: int = 120) -> dict[str, Any]:
    snap = snapshot or {}
    reasons = []
    if not snap:
        return {"ok": False, "reasons": ["snapshot_missing"], "api_health": "critical"}
    ts_raw = snap.get("timestamp")
    ts = None
    if isinstance(ts_raw, str):
        try:
            ts = datetime.fromisoformat(ts_raw)
        except Exception:
            reasons.append("snapshot_timestamp_invalid")
    if ts is not None and datetime.now(timezone.utc) - ts.astimezone(timezone.utc) > timedelta(seconds=max_age_seconds):
        reasons.append("stale_data")
    if not snap.get("account"):
        reasons.append("missing_account")
    if snap.get("positions") is None:
        reasons.append("missing_positions")
    if snap.get("watchlist") is None:
        reasons.append("missing_watchlist")
    return {"ok": len(reasons) == 0, "reasons": reasons, "api_health": "ok" if len(reasons) == 0 else "degraded"}
