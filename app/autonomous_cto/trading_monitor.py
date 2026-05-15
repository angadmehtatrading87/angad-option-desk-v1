from __future__ import annotations

import json
from datetime import datetime, timezone

from app.autonomous_cto.runtime_monitor import get_recent_worker_logs
from app.autonomous_cto.reject_reason_analyzer import analyze_skip_reasons
from app.autonomous_cto.utilization_analyzer import parse_capital_utilization, compute_avg_utilization


def get_recent_trade_activity(hours: int = 24) -> dict:
    log_text = get_recent_worker_logs("ig-execution-worker", lines=500)
    decisions = 0
    skips = 0
    submitted = 0
    simulated = 0
    confirmed = 0
    rejected = 0
    cooldown = 0
    last_trade_ts: str | None = None

    for line in log_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        stage = obj.get("stage", "")
        if stage == "eligible":
            decisions += obj.get("decision_count", 0)
            skips += obj.get("skip_count", 0)
        if stage == "run":
            for sub in obj.get("submitted") or []:
                status = str(sub.get("status", "")).upper()
                submitted += 1
                if status in ("SIMULATED", "CONFIRMED_IN_BOOK", "ACCEPTED_NOT_VISIBLE_IN_BOOK"):
                    simulated += 1
                    if last_trade_ts is None:
                        last_trade_ts = obj.get("ts")
                elif status == "CONFIRM_REJECTED":
                    rejected += 1
                elif status == "SKIPPED_REENTRY_COOLDOWN":
                    cooldown += 1
                elif status == "CONFIRMED":
                    confirmed += 1

    skip_reasons = analyze_skip_reasons(log_text)
    util_records = parse_capital_utilization(log_text)

    return {
        "decisions_attempted": decisions,
        "skips": skips,
        "submitted": submitted,
        "simulated_or_confirmed": simulated + confirmed,
        "ig_rejected": rejected,
        "cooldown_blocked": cooldown,
        "skip_reasons": skip_reasons,
        "avg_utilization": compute_avg_utilization(util_records),
        "last_trade_ts": last_trade_ts,
        "log_lines_parsed": len([l for l in log_text.splitlines() if l.strip()]),
    }


def detect_trade_drought(activity: dict, threshold_hours: int = 4) -> bool:
    last_ts = activity.get("last_trade_ts")
    if not last_ts:
        return True
    try:
        last = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        hours_ago = (now - last).total_seconds() / 3600
        return hours_ago > threshold_hours
    except Exception:
        return True


def get_skip_reason_breakdown(hours: int = 24) -> dict:
    log_text = get_recent_worker_logs("ig-execution-worker", lines=300)
    return analyze_skip_reasons(log_text)


def get_submission_outcomes(hours: int = 24) -> dict:
    activity = get_recent_trade_activity(hours)
    return {
        "submitted": activity["submitted"],
        "executed": activity["simulated_or_confirmed"],
        "ig_rejected": activity["ig_rejected"],
        "cooldown_blocked": activity["cooldown_blocked"],
    }


def get_current_positions() -> list:
    try:
        from app.ig_api_governor import get_ig_cached_snapshot
        snapshot = get_ig_cached_snapshot(force_refresh=False) or {}
        return snapshot.get("positions") or []
    except Exception:
        return []


def compute_trading_health(activity: dict, positions: list) -> dict:
    score = 100.0
    issues = []

    if activity["decisions_attempted"] == 0:
        score -= 40
        issues.append("no_eligible_decisions")
    elif activity["simulated_or_confirmed"] == 0 and activity["submitted"] == 0:
        score -= 30
        issues.append("no_trades_submitted")

    if detect_trade_drought(activity, threshold_hours=4):
        score -= 20
        issues.append("trade_drought_4h")

    if activity["avg_utilization"] < 0.05:
        score -= 15
        issues.append("near_zero_capital_utilization")

    skip_total = sum(activity["skip_reasons"].values()) if activity["skip_reasons"] else 0
    if skip_total > 50 and activity["simulated_or_confirmed"] == 0:
        score -= 15
        issues.append("high_skip_rate_zero_executions")

    return {
        "score": max(0.0, round(score, 1)),
        "issues": issues,
        "positions": len(positions),
    }
