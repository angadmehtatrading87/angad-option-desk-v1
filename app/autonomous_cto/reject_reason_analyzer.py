from __future__ import annotations

import json
import os
import re
from typing import Any

KNOWN_BLOCKERS = [
    "weak_setup_watch_or_reject",
    "score_below_high_threshold",
    "confidence_below_threshold",
    "small_trade_suppressed",
    "risk_reward_not_acceptable",
    "bad_spread_friction",
    "ig_login_failed",
    "api_timeout",
    "ig_account_switch_failed",
    "disabled_per_backtest_for_pair",
    "reentry_cooldown_active",
    "safety_blocked",
    "snapshot_unavailable",
    "missing_trade_thesis",
    "liquidity_reserve_protection",
]


def analyze_skip_reasons(log_text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in log_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        skips = obj.get("skips") or []
        for skip in skips:
            reason_str = str(skip.get("reason") or "")
            for r in reason_str.split(","):
                r = r.strip()
                if r:
                    counts[r] = counts.get(r, 0) + 1
        # Also capture top-level reason arrays
        reasons = obj.get("reason") or []
        if isinstance(reasons, list):
            for r in reasons:
                r = str(r).strip()
                if r:
                    counts[r] = counts.get(r, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def detect_dominant_blocker(reason_counts: dict[str, int]) -> str:
    if not reason_counts:
        return "no_data"
    return max(reason_counts, key=lambda k: reason_counts[k])


def suggest_threshold_adjustments(reason_counts: dict[str, int], current_config: dict) -> list[dict]:
    suggestions = []
    total = sum(reason_counts.values()) or 1

    if reason_counts.get("score_below_high_threshold", 0) / total > 0.3:
        current = float(current_config.get("MARKET_BRAIN_HIGH_THRESHOLD", 65))
        suggestions.append({
            "param": "MARKET_BRAIN_HIGH_THRESHOLD",
            "current": current,
            "suggested": max(35.0, current - 10.0),
            "rationale": "score_below_high_threshold is dominant blocker; lowering threshold increases eligible trades",
            "env_var": "MARKET_BRAIN_HIGH_THRESHOLD",
        })

    if reason_counts.get("confidence_below_threshold", 0) / total > 0.3:
        current = float(current_config.get("MARKET_BRAIN_CONFIDENCE_THRESHOLD", 60))
        suggestions.append({
            "param": "MARKET_BRAIN_CONFIDENCE_THRESHOLD",
            "current": current,
            "suggested": max(30.0, current - 8.0),
            "rationale": "confidence_below_threshold is dominant blocker",
            "env_var": "MARKET_BRAIN_CONFIDENCE_THRESHOLD",
        })

    if reason_counts.get("risk_reward_not_acceptable", 0) / total > 0.2:
        current = float(current_config.get("MARKET_BRAIN_RR_THRESHOLD", 1.3))
        suggestions.append({
            "param": "MARKET_BRAIN_RR_THRESHOLD",
            "current": current,
            "suggested": max(0.6, current - 0.2),
            "rationale": "risk_reward_not_acceptable is a frequent blocker; lowering RR threshold helps",
            "env_var": "MARKET_BRAIN_RR_THRESHOLD",
        })

    if reason_counts.get("small_trade_suppressed", 0) / total > 0.2:
        suggestions.append({
            "param": "MARKET_BRAIN_DATA_COLLECTION_MODE",
            "current": False,
            "suggested": True,
            "rationale": "small_trade_suppressed is frequently firing; enable data-collection mode to bypass size gate",
            "env_var": "MARKET_BRAIN_DATA_COLLECTION_MODE",
        })

    return suggestions
