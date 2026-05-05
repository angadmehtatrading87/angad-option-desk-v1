"""
IG-FX briefing builder.

Pulls live state from the existing v2 orchestrator + cost-cap meter + IG snapshot
and produces two Telegram-friendly HTML messages:

    build_pre_session_briefing()  → fired ~30 min before London or NY open
    build_post_session_recap()    → fired ~30 min after NY close

This replaces the legacy `app/owner_briefing.py` which was an
equities-options pre-session message that no longer applies in our IG-only
FX setup.

Pure functions: no I/O side-effects, no Telegram sends here. The worker
(`ig_briefing_worker.py`) calls these and dispatches.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

DXB = ZoneInfo("Asia/Dubai")


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _money(v: Any) -> str:
    n = _safe_float(v)
    return f"${n:,.0f}" if abs(n) >= 100 else f"${n:,.2f}"


def _pct(v: Any, decimals: int = 2) -> str:
    return f"{_safe_float(v):.{decimals}f}%"


def _safe_get_v2_plan() -> dict:
    """Run the v2 orchestrator. Returns an empty-ish dict on any error so the
    briefing degrades gracefully rather than crashing the worker."""
    try:
        from app.agent_v2_orchestrator import build_agent_v2_plan
        plan = build_agent_v2_plan() or {}
    except Exception as e:
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "regime": {},
            "deployment": {},
            "candidates": [],
            "account": {},
            "mtf_diagnostics": {},
        }
    return plan


def _safe_get_cost_cap() -> dict:
    try:
        from app.cost_cap_meter import snapshot
        return snapshot()
    except Exception:
        return {"rows": [], "kill_switches": {}}


def _safe_get_ig_account() -> dict:
    try:
        from app.ig_api_governor import get_ig_cached_snapshot
        snap = get_ig_cached_snapshot(force_refresh=False) or {}
        return snap.get("account") or {}
    except Exception:
        return {}


def _safe_get_open_positions_count() -> int:
    try:
        from app.ig_api_governor import get_ig_cached_snapshot
        snap = get_ig_cached_snapshot(force_refresh=False) or {}
        positions = ((snap.get("positions") or {}).get("positions") or [])
        return len(positions)
    except Exception:
        return 0


def _format_session_label(now_dxb: datetime) -> str:
    """Rough session label based on Dubai time."""
    h = now_dxb.hour
    if 3 <= h < 11:
        return "Asia"
    if 11 <= h < 17:
        return "London"
    if 17 <= h < 1:
        return "New York"
    if h >= 1 or h < 3:
        return "Late NY / Asia open"
    return "Off-hours"


def _format_minutes_until(target_hour_dxb: int, now_dxb: datetime) -> str:
    if now_dxb.hour < target_hour_dxb:
        delta_minutes = (target_hour_dxb - now_dxb.hour) * 60 - now_dxb.minute
    else:
        delta_minutes = (24 - now_dxb.hour + target_hour_dxb) * 60 - now_dxb.minute
    h = delta_minutes // 60
    m = delta_minutes % 60
    return f"{h}h {m}m"


def build_pre_session_briefing() -> str:
    """Pre-session Telegram message. Pulled before each major session open."""
    now = datetime.now(DXB)
    plan = _safe_get_v2_plan()
    cost = _safe_get_cost_cap()
    account = _safe_get_ig_account() or plan.get("account") or {}

    if not plan.get("ok"):
        # Honest degraded message rather than fake confidence.
        return (
            f"<b>🤖 IG-FX Pre-Session Briefing</b>\n"
            f"<i>{now.strftime('%Y-%m-%d %H:%M')} Dubai</i>\n\n"
            f"⚠️ Engine returned no plan this cycle.\n"
            f"Reason: <code>{plan.get('error', 'unknown')}</code>\n\n"
            f"The trader will keep retrying every 30s. If this persists, "
            f"check the worker logs."
        )

    regime = plan.get("regime") or {}
    deployment = plan.get("deployment") or {}
    book = plan.get("book_directive") or {}
    candidates = plan.get("candidates") or []
    mtf_diag = plan.get("mtf_diagnostics") or {}

    equity = _safe_float(account.get("equity"))
    available = _safe_float(account.get("available"))
    open_pnl = _safe_float(account.get("open_pnl"))
    open_positions = _safe_get_open_positions_count()

    cost_lines = []
    for row in cost.get("rows", []):
        cat = row.get("category", "")
        pct = _safe_float(row.get("pct"))
        if cat in ("ig_api_calls", "ig_orders_submitted", "llm_usd"):
            cost_lines.append(f"  • {cat}: {pct:.0f}% of cap")
    kill = cost.get("kill_switches") or {}
    kill_warn = ""
    if kill.get("trading_killed"):
        kill_warn = "\n⛔ <b>TRADING KILL-SWITCH ACTIVE</b>"
    elif kill.get("llm_calls_killed"):
        kill_warn = "\n⚠️ LLM kill-switch active — analyzer offline today"

    real_mtf_count = sum(
        1 for d in mtf_diag.values()
        if isinstance(d, dict) and not d.get("degraded", True)
    )
    total_pairs = len(mtf_diag) if mtf_diag else 0
    mtf_status = (
        f"{real_mtf_count}/{total_pairs} pairs on real candles"
        if total_pairs else "no MTF data this cycle"
    )

    lines = []
    lines.append(f"<b>🤖 IG-FX Pre-Session Briefing</b>")
    lines.append(f"<i>{now.strftime('%Y-%m-%d %H:%M')} Dubai · session: {_format_session_label(now)}</i>")
    lines.append("")

    lines.append(f"<b>Account</b>")
    lines.append(f"  Equity: {_money(equity)}")
    lines.append(f"  Available: {_money(available)}")
    lines.append(f"  Open P&L: {_money(open_pnl)}  ·  Open positions: {open_positions}")
    lines.append("")

    lines.append(f"<b>Regime</b>  {regime.get('regime', '—')} (quality {regime.get('quality_score', '—')})")
    if regime.get("notes"):
        for note in (regime.get("notes") or [])[:2]:
            lines.append(f"  · {note}")
    lines.append("")

    lines.append(f"<b>Deployment doctrine</b>")
    lines.append(f"  Mode: {deployment.get('mode', '—')}")
    lines.append(f"  Target deployment: {deployment.get('target_pct', '—')}%  ·  Floor: {deployment.get('floor_pct', '—')}%")
    if book.get("target_position_count") is not None:
        lines.append(f"  Target book size: {book.get('target_position_count')} positions")
    lines.append("")

    if candidates:
        lines.append(f"<b>Top {len(candidates)} candidates</b>")
        for c in candidates:
            sym = c.get("symbol") or "—"
            direction = c.get("direction") or "—"
            score = _safe_float(c.get("score"))
            confidence = _safe_float(c.get("confidence"))
            structure = (c.get("structure") or {}).get("bias", "—")
            lines.append(
                f"  • <b>{sym}</b> {direction} · score {score:.0f} · "
                f"conf {confidence:.0f} · structure {structure}"
            )
    else:
        lines.append("<b>Top candidates</b>")
        lines.append("  No A+ setups this cycle — staying flat.")
        # If there are ranked-but-rejected, show a couple to make it clear
        # the engine is working, just disciplined.
        ranked = (plan.get("ranked") or [])[:3]
        if ranked:
            lines.append("")
            lines.append("<i>Watching (below threshold):</i>")
            for r in ranked:
                sym = r.get("symbol") or "—"
                score = _safe_float(r.get("total_score"))
                lines.append(f"  · {sym} score {score:.0f}")
    lines.append("")

    lines.append(f"<b>Data quality</b>")
    lines.append(f"  MTF candles: {mtf_status}")
    if cost_lines:
        lines.append(f"<b>Cost cap usage today</b>")
        lines.extend(cost_lines)
    if kill_warn:
        lines.append(kill_warn)

    return "\n".join(lines)


def build_post_session_recap(prev_equity: float | None = None) -> str:
    """Post-NY-close recap: how did the day go?

    Args:
        prev_equity: previous-day equity to compute day-over-day delta. If
        not provided, the recap omits the delta.
    """
    now = datetime.now(DXB)
    plan = _safe_get_v2_plan()
    cost = _safe_get_cost_cap()
    account = _safe_get_ig_account() or plan.get("account") or {}

    equity = _safe_float(account.get("equity"))
    available = _safe_float(account.get("available"))
    open_pnl = _safe_float(account.get("open_pnl"))
    open_positions = _safe_get_open_positions_count()

    day_delta_str = ""
    if prev_equity is not None:
        delta = equity - _safe_float(prev_equity)
        delta_pct = (delta / _safe_float(prev_equity) * 100.0) if prev_equity else 0.0
        sign = "📈" if delta >= 0 else "📉"
        day_delta_str = f"  {sign} Day Δ: {_money(delta)} ({delta_pct:+.2f}%)\n"

    # Today's recent trade outcomes from ig_trade_log if available
    trade_summary = "  No trades today."
    try:
        from app.ig_trade_store import recent_ig_trade_log
        rows = recent_ig_trade_log(limit=200) or []
        # Filter to today only (Dubai)
        today_iso = now.strftime("%Y-%m-%d")
        todays = [
            r for r in rows
            if str(r.get("created_at") or "").startswith(today_iso)
            or str(r.get("ts") or "").startswith(today_iso)
        ]
        if todays:
            wins = sum(1 for r in todays if str(r.get("status", "")).upper() in ("CONFIRMED_IN_BOOK",))
            losses = sum(1 for r in todays if str(r.get("status", "")).upper() in ("REJECTED", "STALE_PRICE_BLOCKED", "BROKER_DRY_RUN_FAILED"))
            attempted = len(todays)
            trade_summary = (
                f"  Attempted: {attempted}  ·  Confirmed: {wins}  ·  Blocked/rejected: {losses}"
            )
    except Exception:
        pass

    cost_lines = []
    for row in cost.get("rows", []):
        cat = row.get("category", "")
        used = row.get("used", 0)
        cap = row.get("cap", 0)
        pct = _safe_float(row.get("pct"))
        if cat in ("ig_api_calls", "ig_orders_submitted", "llm_tokens", "llm_usd"):
            unit = "$" if cat == "llm_usd" else ""
            cost_lines.append(f"  • {cat}: {unit}{used:,.2f} / {unit}{cap:,.0f} ({pct:.0f}%)")

    lines = []
    lines.append(f"<b>📊 IG-FX Day Recap</b>")
    lines.append(f"<i>{now.strftime('%Y-%m-%d %H:%M')} Dubai · post-NY close</i>")
    lines.append("")
    lines.append(f"<b>Account</b>")
    lines.append(f"  Equity: {_money(equity)}")
    lines.append(f"  Available: {_money(available)}")
    if day_delta_str:
        lines.append(day_delta_str.rstrip("\n"))
    lines.append(f"  Open P&L: {_money(open_pnl)}  ·  Open positions: {open_positions}")
    lines.append("")
    lines.append(f"<b>Today's activity</b>")
    lines.append(trade_summary)
    lines.append("")

    if plan.get("ok"):
        regime = plan.get("regime") or {}
        lines.append(f"<b>End-of-day read</b>")
        lines.append(f"  Regime: {regime.get('regime', '—')} (quality {regime.get('quality_score', '—')})")
        ls = plan.get("loss_governor") or {}
        if ls.get("evidence_multiplier", 1) > 1:
            lines.append(f"  ⚠️ Loss governor active — evidence threshold ×{ls.get('evidence_multiplier')}")
        lines.append("")

    if cost_lines:
        lines.append(f"<b>Today's cost-cap usage</b>")
        lines.extend(cost_lines)

    kill = cost.get("kill_switches") or {}
    if kill.get("trading_killed") or kill.get("llm_calls_killed"):
        lines.append("")
        if kill.get("trading_killed"):
            lines.append("⛔ Trading kill-switch tripped today — review tomorrow morning.")
        if kill.get("llm_calls_killed"):
            lines.append("⚠️ LLM kill-switch tripped — analyzer was offline.")

    lines.append("")
    lines.append("<i>Counters reset 00:00 Dubai. Next briefing: pre-London open ~06:30.</i>")

    return "\n".join(lines)
