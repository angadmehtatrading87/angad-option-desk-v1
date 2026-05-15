from __future__ import annotations

import json
import os
import time
import traceback

import requests

from app.autonomous_cto import state_store

TELEGRAM_API = "https://api.telegram.org"
_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_ALLOWED_CHAT_ID = str(os.getenv("TELEGRAM_ALLOWED_CHAT_ID", ""))


def send_cto_message(text: str) -> None:
    try:
        from app.telegram_alerts import send_telegram_message
        send_telegram_message(text)
    except Exception:
        # Direct fallback
        if _BOT_TOKEN and _ALLOWED_CHAT_ID:
            requests.post(
                f"{TELEGRAM_API}/bot{_BOT_TOKEN}/sendMessage",
                json={"chat_id": _ALLOWED_CHAT_ID, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )


def _get_updates(offset: int) -> list[dict]:
    try:
        r = requests.get(
            f"{TELEGRAM_API}/bot{_BOT_TOKEN}/getUpdates",
            params={"timeout": 20, "offset": offset},
            timeout=30,
        )
        if not r.ok:
            return []
        return r.json().get("result") or []
    except Exception:
        return []


def _is_authorized(chat_id: str) -> bool:
    return not _ALLOWED_CHAT_ID or str(chat_id) == _ALLOWED_CHAT_ID


def _handle_command(chat_id: str, text: str) -> str:
    if not _is_authorized(chat_id):
        return "Unauthorized."
    cmd, _, arg = (text or "").strip().partition(" ")
    cmd = cmd.lower()

    if cmd == "/ops":
        return _render_ops()
    if cmd == "/cto":
        return _render_cto_status()
    if cmd == "/performance":
        return _render_performance()
    if cmd == "/capital":
        return _render_capital()
    if cmd == "/positions":
        return _render_positions()
    if cmd == "/why_no_trade":
        return _render_why_no_trade()
    if cmd == "/github":
        return _render_github()
    if cmd == "/deploy_status":
        return _render_deploy_status()
    if cmd == "/kill":
        return _handle_kill()
    if cmd == "/feedback":
        return _handle_feedback(arg.strip(), chat_id)
    if cmd == "/tasks":
        return _render_tasks()
    if cmd == "/approve" and arg.strip().isdigit():
        return _handle_approve(int(arg.strip()))
    return "Unknown CTO command. Try /ops /cto /why_no_trade /feedback <text> /kill"


def _render_ops() -> str:
    from app.autonomous_cto.runtime_monitor import check_service_health
    health = check_service_health()
    score = health.get("score", 0)
    services = health.get("services") or {}
    lines = [f"<b>Runtime Health: {score}/100</b>"]
    for svc, state in services.items():
        icon = "✅" if state == "active" else "❌"
        lines.append(f"{icon} {svc}: {state}")
    return "\n".join(lines)


def _render_cto_status() -> str:
    killed = state_store.get_kv("cto_killed", False)
    tasks = state_store.get_pending_tasks(limit=5)
    decisions = state_store.get_recent_decisions(limit=5)
    patches = state_store.patches_today()
    lines = [
        f"<b>CTO Agent Status</b>",
        f"🔴 KILLED" if killed else "🟢 ACTIVE",
        f"Patches today: {patches}",
        f"Pending tasks: {len(tasks)}",
        "",
        "<b>Recent decisions:</b>",
    ]
    for d in decisions[:3]:
        lines.append(f"• [{d.get('decision_type')}] {d.get('summary', '')[:50]}")
    return "\n".join(lines)


def _render_performance() -> str:
    from app.autonomous_cto.trading_monitor import get_recent_trade_activity, detect_trade_drought
    activity = get_recent_trade_activity()
    drought = detect_trade_drought(activity)
    lines = [
        "<b>Trading Performance (24h)</b>",
        f"Decisions attempted: {activity.get('decisions_attempted', 0)}",
        f"Trades executed: {activity.get('simulated_or_confirmed', 0)}",
        f"IG rejected: {activity.get('ig_rejected', 0)}",
        f"Cooldown blocked: {activity.get('cooldown_blocked', 0)}",
        f"Capital utilization: {activity.get('avg_utilization', 0):.1%}",
        f"Trade drought: {'⚠️ YES' if drought else '✅ NO'}",
    ]
    return "\n".join(lines)


def _render_capital() -> str:
    from app.autonomous_cto.trading_monitor import get_recent_trade_activity
    from app.autonomous_cto.utilization_analyzer import parse_capital_utilization
    from app.autonomous_cto.runtime_monitor import get_recent_worker_logs
    log = get_recent_worker_logs("ig-execution-worker", lines=100)
    records = parse_capital_utilization(log)
    if not records:
        return "No capital utilization data available."
    latest = records[-1]
    lines = [
        "<b>Capital Utilization</b>",
        f"Available: ${latest.get('available_capital', 0):,.0f}",
        f"Deployable: ${latest.get('deployable_capital', 0):,.0f}",
        f"Used: ${latest.get('current_used_capital', 0):,.0f}",
        f"Utilization: {latest.get('actual_utilization', 0):.1%}",
    ]
    return "\n".join(lines)


def _render_positions() -> str:
    from app.autonomous_cto.trading_monitor import get_current_positions
    positions = get_current_positions()
    if not positions:
        return "No open positions."
    lines = [f"<b>Open Positions ({len(positions)})</b>"]
    for p in positions[:10]:
        lines.append(f"• {p.get('epic', '?')} {p.get('direction', '?')} sz={p.get('size', '?')}")
    return "\n".join(lines)


def _render_why_no_trade() -> str:
    from app.autonomous_cto.trading_monitor import get_skip_reason_breakdown
    from app.autonomous_cto.reject_reason_analyzer import detect_dominant_blocker, suggest_threshold_adjustments
    reasons = get_skip_reason_breakdown()
    dominant = detect_dominant_blocker(reasons)
    suggestions = suggest_threshold_adjustments(reasons, {})
    lines = [f"<b>Why No Trade?</b>", f"Dominant blocker: <code>{dominant}</code>", ""]
    for r, c in list(reasons.items())[:6]:
        lines.append(f"• {r}: {c}")
    if suggestions:
        lines.append("\n<b>Suggested fixes:</b>")
        for s in suggestions[:3]:
            lines.append(f"• {s.get('param')}: {s.get('current')} → {s.get('suggested')}")
    return "\n".join(lines)


def _render_github() -> str:
    from app.autonomous_cto.github_monitor import list_open_prs, list_recent_workflow_runs
    prs = list_open_prs()
    runs = list_recent_workflow_runs(limit=3)
    lines = [f"<b>GitHub Status</b>", f"Open PRs: {len(prs)}"]
    for pr in prs[:3]:
        lines.append(f"• #{pr.get('number')} {pr.get('title', '')[:40]}")
    lines.append("\n<b>Recent CI runs:</b>")
    for run in runs[:3]:
        icon = "✅" if run.get("conclusion") == "success" else ("🔄" if run.get("status") == "in_progress" else "❌")
        lines.append(f"{icon} {run.get('name', '?')[:30]} ({run.get('headBranch', '?')[:20]})")
    return "\n".join(lines)


def _render_deploy_status() -> str:
    from app.autonomous_cto.runtime_monitor import get_deployed_sha
    sha = get_deployed_sha()
    last_deploy = state_store.get_kv("last_deploy_sha", "unknown")
    decisions = [d for d in state_store.get_recent_decisions(limit=10) if d.get("decision_type") == "deploy"]
    lines = [
        "<b>Deploy Status</b>",
        f"Lightsail HEAD: <code>{sha}</code>",
        f"Last auto-deploy SHA: <code>{last_deploy}</code>",
    ]
    if decisions:
        d = decisions[0]
        lines.append(f"Last deploy: {d.get('created_at', '')[:16]} → {d.get('outcome')}")
    return "\n".join(lines)


def _handle_kill() -> str:
    state_store.set_kv("cto_killed", True)
    state_store.log_event("kill_activated", "critical", "kill switch activated via Telegram")
    return "🔴 CTO agent KILLED. Autonomous actions suspended. Send /resume_cto to re-enable."


def _handle_feedback(text: str, chat_id: str) -> str:
    if not text:
        return "Usage: /feedback <your feedback>"
    from app.autonomous_cto.feedback_ingestor import ingest_feedback
    result = ingest_feedback(text, source=f"telegram:{chat_id}")
    return f"✅ Feedback logged as task #{result.get('task_id')}: {result.get('title')}"


def _render_tasks() -> str:
    tasks = state_store.get_pending_tasks(limit=10)
    if not tasks:
        return "No pending improvement tasks."
    lines = ["<b>Pending Tasks</b>"]
    for t in tasks:
        lines.append(f"#{t['id']} P{t['priority']} [{t['status']}] {t['title'][:50]}")
    return "\n".join(lines)


def _handle_approve(task_id: int) -> str:
    state_store.update_task_status(task_id, "approved")
    return f"✅ Task #{task_id} approved and queued for execution."


def run_telegram_loop() -> None:
    offset_key = "cto_telegram_offset"
    offset = int(state_store.get_kv(offset_key) or 0)

    while True:
        try:
            updates = _get_updates(offset)
            for update in updates:
                update_id = update.get("update_id", 0)
                offset = update_id + 1
                state_store.set_kv(offset_key, offset)

                msg = update.get("message") or {}
                chat_id = str((msg.get("chat") or {}).get("id", ""))
                text = str(msg.get("text") or "").strip()
                if text.startswith("/"):
                    reply = _handle_command(chat_id, text)
                    if reply and chat_id:
                        requests.post(
                            f"{TELEGRAM_API}/bot{_BOT_TOKEN}/sendMessage",
                            json={"chat_id": chat_id, "text": reply, "parse_mode": "HTML"},
                            timeout=10,
                        )
        except Exception:
            pass
        time.sleep(1)
