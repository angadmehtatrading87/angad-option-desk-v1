import os
import json
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from app.owner_briefing import build_pre_session_briefing
from app.virtual_portfolio import virtual_account_snapshot

DXB = ZoneInfo("Asia/Dubai")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")
STATE_PATH = os.path.join(BASE_DIR, "data", "reporting_state.json")

def _now_dxb():
    return datetime.now(DXB)

def _today_dxb():
    return _now_dxb().date().isoformat()

def _load_state():
    if not os.path.exists(STATE_PATH):
        return {
            "last_pre_session_sent_for": None,
            "last_post_session_sent_for": None,
            "withdrawal_pool": 0.0,
        }
    with open(STATE_PATH, "r") as f:
        return json.load(f)

def _save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

def today_closed_trades():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT id, trade_id, symbol, strategy, realized_pnl, opened_at, closed_at, notes
        FROM virtual_positions
        WHERE status = 'CLOSED'
        ORDER BY id DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    today = _today_dxb()
    out = []
    for r in rows:
        closed_at = str(r.get("closed_at") or "")
        if closed_at[:10] == today:
            out.append(r)
    return out

def today_realized_pnl():
    trades = today_closed_trades()
    total = 0.0
    for t in trades:
        total += float(t.get("realized_pnl") or 0.0)
    return round(total, 2), trades

def build_owner_post_session_report():
    state = _load_state()
    snap = virtual_account_snapshot()
    realized_today, closed = today_realized_pnl()

    withdrawal_pool = float(state.get("withdrawal_pool", 0.0))
    projected_withdrawal_pool = round(withdrawal_pool + realized_today, 2) if realized_today > 0 else withdrawal_pool

    lines = []
    lines.append("<b>Post-Session Report</b>")
    lines.append("")
    lines.append(f"Date: {_today_dxb()}")
    lines.append(f"Realized P&L Today: ${realized_today:,.2f}")
    lines.append(f"Unrealized P&L: ${float(snap.get('unrealized_pnl', 0) or 0):,.2f}")
    lines.append(f"Cash Balance: ${float(snap.get('cash_balance', 0) or 0):,.2f}")
    lines.append(f"Total Equity: ${float(snap.get('total_equity', 0) or 0):,.2f}")
    lines.append(f"Open Positions: {len(snap.get('open_positions', []))}")
    lines.append(f"Withdrawal Pool (projected): ${projected_withdrawal_pool:,.2f}")
    lines.append("")

    lines.append("<b>Trades Taken / Closed Today</b>")
    if closed:
        for t in closed[:20]:
            note = (t.get("notes") or "").strip()
            lines.append(
                f"- {t.get('symbol')} | trade #{t.get('trade_id')} | "
                f"{t.get('strategy')} | realized ${float(t.get('realized_pnl') or 0):,.2f}"
            )
            if note:
                lines.append(f"  Why / exit note: {note}")
    else:
        lines.append("- No closed trades today.")

    lines.append("")
    lines.append("<b>Why They Were Taken</b>")
    lines.append("- Refer to session plan focus symbols, regime alignment, structure preference, and autonomous execution filter.")
    lines.append("")
    lines.append("<b>Commentary</b>")
    if realized_today > 0:
        lines.append("- Positive day. Profit eligible for withdrawal pool under current policy.")
    elif realized_today < 0:
        lines.append("- Negative day. Tighten selection and review entry quality against regime fit.")
    else:
        lines.append("- Flat/open-book day. Preserve capital if edge is unclear.")

    return "\n".join(lines), projected_withdrawal_pool

def mark_pre_session_sent():
    state = _load_state()
    state["last_pre_session_sent_for"] = _today_dxb()
    _save_state(state)

def mark_post_session_sent(new_withdrawal_pool=None):
    state = _load_state()
    state["last_post_session_sent_for"] = _today_dxb()
    if new_withdrawal_pool is not None:
        state["withdrawal_pool"] = float(new_withdrawal_pool)
    _save_state(state)

def pre_session_due():
    state = _load_state()
    return state.get("last_pre_session_sent_for") != _today_dxb()

def post_session_due():
    state = _load_state()
    return state.get("last_post_session_sent_for") != _today_dxb()

def get_pre_session_message():
    return build_pre_session_briefing()
