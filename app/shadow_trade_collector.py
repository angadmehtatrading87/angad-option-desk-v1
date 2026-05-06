"""
Shadow trade collector.

Records what the bot WOULD have submitted at looser thresholds, in
parallel to live decisions, without actually placing those trades.

How it's used:
    Hook called from `market_brain_execution_bridge.build_market_brain_execution_pick`
    after the live decision set is computed but before execution. We rerun
    the same opportunities at lower thresholds and append a JSONL record
    per shadow-decision to `data/shadow_trades.jsonl`. The actual live
    decision flow is untouched.

Why it matters:
    On quiet days the live bot takes 0 trades. With shadow recording we
    still get N decisions/day to learn from at multiple threshold tiers.
    After a week we can analyze the shadow trades vs subsequent price
    action and tune the live thresholds based on real signal distribution.

Storage format (JSONL — one record per line):
    {
      "ts": "2026-05-06T15:42:00+04:00",
      "tier": "live" | "loose" | "very_loose",
      "thresholds": {"score": 65, "confidence": 60},
      "epic": "CS.D.EURUSD.DBM.IP",
      "direction": "long",
      "score": 52.34,
      "confidence": 48.16,
      "would_trade": false,
      "rationale": "score below tier threshold",
    }
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

DXB = ZoneInfo("Asia/Dubai")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(BASE_DIR, "data", "shadow_trades.jsonl")

# Threshold tiers tested in parallel to the live thresholds.
# `live` is just a recording of the bot's actual configured threshold so we
# have a clean side-by-side. `loose` and `very_loose` are progressively more
# permissive.
TIERS = [
    {"name": "live",        "score": 74.0, "confidence": 72.0},
    {"name": "loose",       "score": 65.0, "confidence": 60.0},
    {"name": "very_loose",  "score": 55.0, "confidence": 50.0},
]


def _now() -> datetime:
    return datetime.now(DXB)


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _append_record(record: dict) -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def record_shadow(opportunities: list[dict], live_decisions: list[dict]) -> int:
    """
    Called once per orchestrator cycle.

    Args:
        opportunities: the full list of pre-threshold opportunities the
                       orchestrator scored. Each dict should have at least
                       `epic`, `direction`, `score`, `confidence`. Match the
                       shape from `build_market_brain_execution_pick`'s
                       intermediate `out.opportunities`.
        live_decisions: what actually got past the live threshold (so we can
                        flag tier="live" entries as would_trade=true).

    Returns: number of records written.
    """
    if not opportunities:
        return 0

    live_epics = {d.get("epic") for d in live_decisions if isinstance(d, dict)}
    ts = _now().isoformat()
    written = 0

    for opp in opportunities:
        epic = opp.get("epic") if isinstance(opp, dict) else getattr(opp, "epic", None)
        direction = opp.get("direction") if isinstance(opp, dict) else getattr(opp, "direction", None)
        score = _safe_float(opp.get("opportunity_score") if isinstance(opp, dict) else getattr(opp, "opportunity_score", None))
        confidence = _safe_float(opp.get("confidence_score") if isinstance(opp, dict) else getattr(opp, "confidence_score", None))

        if not epic:
            continue

        for tier in TIERS:
            would_trade = (score >= tier["score"]) and (confidence >= tier["confidence"])
            # The "live" tier is special — we record what actually happened
            # rather than recomputing.
            if tier["name"] == "live":
                would_trade = epic in live_epics

            rationale_parts = []
            if score < tier["score"]:
                rationale_parts.append(f"score {score:.1f} < {tier['score']:.0f}")
            if confidence < tier["confidence"]:
                rationale_parts.append(f"conf {confidence:.1f} < {tier['confidence']:.0f}")
            rationale = "; ".join(rationale_parts) or "passed thresholds"

            record = {
                "ts": ts,
                "tier": tier["name"],
                "thresholds": {"score": tier["score"], "confidence": tier["confidence"]},
                "epic": epic,
                "direction": direction,
                "score": round(score, 2),
                "confidence": round(confidence, 2),
                "would_trade": bool(would_trade),
                "rationale": rationale,
            }
            try:
                _append_record(record)
                written += 1
            except Exception:
                # Never let a logging failure block live trading
                pass

    return written


def summarize_window(hours: int = 24) -> dict:
    """Quick stats over recent shadow records — useful for the briefing."""
    if not os.path.exists(LOG_PATH):
        return {"records": 0, "by_tier": {}}

    from datetime import timedelta
    cutoff = _now() - timedelta(hours=hours)
    cutoff_iso = cutoff.isoformat()

    by_tier: dict[str, dict] = {}
    total = 0

    with open(LOG_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("ts", "") < cutoff_iso:
                continue
            total += 1
            tier = rec.get("tier", "unknown")
            t = by_tier.setdefault(tier, {"count": 0, "would_trade": 0})
            t["count"] += 1
            if rec.get("would_trade"):
                t["would_trade"] += 1

    return {"records": total, "by_tier": by_tier, "window_hours": hours}
