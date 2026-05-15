from __future__ import annotations

import json


def parse_capital_utilization(log_text: str) -> list[dict]:
    records = []
    for line in log_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        cap = obj.get("capital_utilization") or {}
        if cap and isinstance(cap, dict):
            records.append({
                "ts": obj.get("ts", ""),
                "actual_utilization": float(cap.get("actual_utilization") or 0.0),
                "deployable_capital": float(cap.get("deployable_capital") or 0.0),
                "available_capital": float(cap.get("available_capital") or 0.0),
                "current_used_capital": float(cap.get("current_used_capital") or 0.0),
            })
    return records


def compute_avg_utilization(util_records: list[dict]) -> float:
    if not util_records:
        return 0.0
    return sum(r["actual_utilization"] for r in util_records) / len(util_records)


def detect_under_utilization(util_records: list[dict], threshold: float = 0.15) -> bool:
    avg = compute_avg_utilization(util_records)
    return avg < threshold


def suggest_utilization_improvements(util_records: list[dict], skip_reasons: dict) -> list[str]:
    suggestions = []
    avg = compute_avg_utilization(util_records)
    total_skips = sum(skip_reasons.values()) if skip_reasons else 0

    if avg < 0.05:
        suggestions.append("Capital utilization near zero — bot is not trading at all. Check execution worker logs for blockers.")
    elif avg < 0.15:
        suggestions.append(f"Under-utilization: avg {avg:.1%}. Target 30-70% for data-collection phase.")

    if total_skips > 100 and avg < 0.10:
        suggestions.append("High skip rate + low utilization: thresholds likely too tight. Consider lowering MARKET_BRAIN_HIGH_THRESHOLD.")

    if util_records:
        deployable = util_records[-1].get("deployable_capital", 0)
        if deployable > 0 and avg < 0.10:
            suggestions.append(f"${deployable:,.0f} deployable capital sitting idle. Enable DATA_COLLECTION_MODE to force deployment.")

    return suggestions
