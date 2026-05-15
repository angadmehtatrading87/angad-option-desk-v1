from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

DXB = ZoneInfo("Asia/Dubai")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")


def _now_str() -> str:
    return datetime.now(DXB).strftime("%Y%m%d")


def _write(filename: str, content: str) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, filename)
    with open(path, "w") as f:
        f.write(content)
    return path


def write_daily_report(diagnosis: dict, decisions: list, tasks: list) -> str:
    date_str = _now_str()
    runtime = diagnosis.get("runtime") or {}
    trading = diagnosis.get("trading") or {}
    activity = trading.get("activity") or {}
    skip = diagnosis.get("skip_analysis") or {}

    lines = [
        f"# CTO Daily Report — {date_str}",
        "",
        f"**Overall Health:** {diagnosis.get('overall_score', '?')}/100",
        f"**Generated:** {datetime.now(DXB).isoformat()}",
        "",
        "## Runtime Health",
        f"- Score: {runtime.get('score')}",
        f"- Services degraded: {runtime.get('degraded', [])}",
        f"- Critical: {runtime.get('critical', [])}",
        "",
        "## Trading Activity (last 24h)",
        f"- Decisions attempted: {activity.get('decisions_attempted', 0)}",
        f"- Trades executed: {activity.get('simulated_or_confirmed', 0)}",
        f"- IG rejected: {activity.get('ig_rejected', 0)}",
        f"- Avg capital utilization: {activity.get('avg_utilization', 0):.1%}",
        f"- Open positions: {trading.get('positions', 0)}",
        "",
        "## Top Skip Reasons",
    ]
    for reason, count in list((skip.get("reason_counts") or {}).items())[:8]:
        lines.append(f"- `{reason}`: {count}")

    lines += ["", "## Autonomous Decisions Today"]
    for d in decisions[:10]:
        lines.append(f"- [{d.get('decision_type')}] {d.get('summary')} → {d.get('outcome')}")

    lines += ["", "## Pending Improvement Tasks"]
    for t in tasks[:10]:
        lines.append(f"- [{t.get('status')}] P{t.get('priority')} {t.get('title')}")

    content = "\n".join(lines) + "\n"
    return _write(f"cto_daily_report_{date_str}.md", content)


def write_trading_gate_report(reject_analysis: dict) -> str:
    date_str = _now_str()
    lines = [
        f"# Trading Gate Report — {date_str}",
        "",
        f"**Dominant Blocker:** `{reject_analysis.get('dominant_blocker', 'unknown')}`",
        "",
        "## Rejection Breakdown",
    ]
    for reason, count in (reject_analysis.get("reason_counts") or {}).items():
        lines.append(f"- `{reason}`: {count}")

    lines += ["", "## Suggested Threshold Adjustments"]
    for s in reject_analysis.get("suggestions") or []:
        lines.append(f"- **{s.get('param')}**: {s.get('current')} → {s.get('suggested')} ({s.get('rationale')})")

    content = "\n".join(lines) + "\n"
    return _write(f"trading_gate_report_{date_str}.md", content)


def write_runtime_health_report(health: dict) -> str:
    date_str = _now_str()
    lines = [
        f"# Runtime Health Report — {date_str}",
        "",
        f"**Score:** {health.get('score')}/100",
        "",
        "## Service Status",
    ]
    for svc, state in (health.get("services") or {}).items():
        icon = "✅" if state == "active" else "❌"
        lines.append(f"- {icon} `{svc}`: {state}")

    content = "\n".join(lines) + "\n"
    return _write(f"runtime_health_report_{date_str}.md", content)


def write_improvement_queue(tasks: list) -> str:
    date_str = _now_str()
    lines = [f"# Improvement Queue — {date_str}", ""]
    for t in tasks:
        lines.append(f"## [{t.get('status')}] {t.get('title')} (P{t.get('priority')})")
        lines.append(f"Source: {t.get('source')} | Created: {t.get('created_at', '')[:10]}")
        lines.append(f"{t.get('description', '')}")
        lines.append("")

    content = "\n".join(lines) + "\n"
    return _write(f"improvement_queue_{date_str}.md", content)
