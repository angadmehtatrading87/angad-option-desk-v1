from __future__ import annotations

import json
from datetime import datetime, timezone

from app.autonomous_cto import runtime_monitor, trading_monitor, reject_reason_analyzer, utilization_analyzer


def run_full_diagnosis() -> dict:
    runtime_health = runtime_monitor.check_service_health()
    log_text = runtime_monitor.get_recent_worker_logs("ig-execution-worker", lines=500)
    activity = trading_monitor.get_recent_trade_activity()
    positions = trading_monitor.get_current_positions()
    trading_health = trading_monitor.compute_trading_health(activity, positions)
    skip_reasons = activity.get("skip_reasons", {})
    util_records = utilization_analyzer.parse_capital_utilization(log_text)
    util_suggestions = utilization_analyzer.suggest_utilization_improvements(util_records, skip_reasons)
    dominant_blocker = reject_reason_analyzer.detect_dominant_blocker(skip_reasons)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runtime": runtime_health,
        "trading": {
            "activity": activity,
            "health": trading_health,
            "positions": len(positions),
        },
        "skip_analysis": {
            "dominant_blocker": dominant_blocker,
            "reason_counts": skip_reasons,
            "utilization_suggestions": util_suggestions,
        },
        "overall_score": score_overall_health({
            "runtime": runtime_health,
            "trading": {"health": trading_health},
        }),
    }


def score_overall_health(diagnosis: dict) -> float:
    runtime_score = float((diagnosis.get("runtime") or {}).get("score", 50))
    trading_score = float(((diagnosis.get("trading") or {}).get("health") or {}).get("score", 50))
    return round(runtime_score * 0.5 + trading_score * 0.5, 1)


def identify_top_issues(diagnosis: dict) -> list[dict]:
    issues = []

    runtime = diagnosis.get("runtime") or {}
    for svc in runtime.get("critical", []):
        issues.append({
            "severity": "critical",
            "area": "runtime",
            "issue": f"core service down: {svc}",
            "suggested_action": f"restart {svc} and investigate logs",
        })
    for svc in runtime.get("degraded", []):
        if svc not in runtime.get("critical", []):
            issues.append({
                "severity": "warning",
                "area": "runtime",
                "issue": f"service degraded: {svc}",
                "suggested_action": f"check {svc} logs for errors",
            })

    trading = (diagnosis.get("trading") or {}).get("health") or {}
    for issue in trading.get("issues", []):
        issues.append({
            "severity": "warning" if "drought" not in issue else "high",
            "area": "trading",
            "issue": issue,
            "suggested_action": _trading_action(issue),
        })

    dominant = (diagnosis.get("skip_analysis") or {}).get("dominant_blocker", "")
    if dominant and dominant != "no_data":
        issues.append({
            "severity": "warning",
            "area": "trading_config",
            "issue": f"dominant skip reason: {dominant}",
            "suggested_action": f"investigate and tune thresholds for {dominant}",
        })

    issues.sort(key=lambda x: {"critical": 0, "high": 1, "warning": 2}.get(x["severity"], 3))
    return issues


def _trading_action(issue: str) -> str:
    actions = {
        "no_eligible_decisions": "lower MARKET_BRAIN thresholds or enable DATA_COLLECTION_MODE",
        "no_trades_submitted": "check execution engine logs for submission errors",
        "trade_drought_4h": "verify market hours and check skip reason breakdown",
        "near_zero_capital_utilization": "enable DATA_COLLECTION_MODE or lower all thresholds",
        "high_skip_rate_zero_executions": "dominant skip reason is blocking all trades; tune the relevant threshold",
    }
    return actions.get(issue, "investigate logs and adjust configuration")


def format_diagnosis_for_llm(diagnosis: dict) -> str:
    runtime = diagnosis.get("runtime") or {}
    trading = diagnosis.get("trading") or {}
    skip = diagnosis.get("skip_analysis") or {}
    issues = identify_top_issues(diagnosis)

    lines = [
        f"DIAGNOSIS TIMESTAMP: {diagnosis.get('timestamp', 'unknown')}",
        f"OVERALL HEALTH SCORE: {diagnosis.get('overall_score', '?')}/100",
        "",
        "RUNTIME:",
        f"  score={runtime.get('score')} degraded={runtime.get('degraded')} critical={runtime.get('critical')}",
        "",
        "TRADING:",
        f"  decisions_attempted={trading.get('activity', {}).get('decisions_attempted')}",
        f"  executed={trading.get('activity', {}).get('simulated_or_confirmed')}",
        f"  ig_rejected={trading.get('activity', {}).get('ig_rejected')}",
        f"  avg_utilization={trading.get('activity', {}).get('avg_utilization', 0):.1%}",
        f"  positions_open={trading.get('positions')}",
        "",
        "TOP SKIP REASONS:",
    ]
    for reason, count in list((skip.get("reason_counts") or {}).items())[:6]:
        lines.append(f"  {reason}: {count}")
    lines.append(f"  dominant_blocker: {skip.get('dominant_blocker')}")
    lines.append("")
    lines.append("TOP ISSUES:")
    for iss in issues[:5]:
        lines.append(f"  [{iss['severity'].upper()}] {iss['issue']} → {iss['suggested_action']}")

    return "\n".join(lines)
