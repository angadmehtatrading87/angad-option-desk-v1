from datetime import datetime
from zoneinfo import ZoneInfo
import sqlite3
import os

from app.virtual_portfolio import virtual_account_snapshot
from app.trading_window import trading_window_status

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")
DXB = ZoneInfo("Asia/Dubai")

def today_dxb():
    return datetime.now(DXB).date().isoformat()

def today_trade_stats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    today = today_dxb()

    cur.execute("""
        SELECT status, COUNT(*) as cnt
        FROM trade_proposals
        WHERE substr(created_at, 1, 10) = ?
        GROUP BY status
    """, (today,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    stats = {
        "total": 0,
        "pending": 0,
        "approved": 0,
        "rejected": 0,
        "watch_only": 0,
        "blocked": 0,
        "virtual_open": 0,
        "virtual_stale_blocked": 0,
    }

    for r in rows:
        status = (r["status"] or "").upper()
        cnt = int(r["cnt"])
        stats["total"] += cnt

        if status == "PENDING_APPROVAL":
            stats["pending"] += cnt
        elif status == "APPROVED_BY_USER":
            stats["approved"] += cnt
        elif status == "REJECTED":
            stats["rejected"] += cnt
        elif status == "WATCH_ONLY":
            stats["watch_only"] += cnt
        elif status == "BLOCKED":
            stats["blocked"] += cnt
        elif status == "VIRTUAL_OPEN":
            stats["virtual_open"] += cnt
        elif status == "VIRTUAL_STALE_BLOCKED":
            stats["virtual_stale_blocked"] += cnt

    return stats

def build_start_of_day_summary():
    snap = virtual_account_snapshot()
    tw = trading_window_status()
    stats = today_trade_stats()

    return (
        f"<b>Day Start Summary — Virtual Production</b>\n\n"
        f"Date: {today_dxb()}\n"
        f"Dubai Time: {tw['now_dubai']}\n\n"
        f"<b>Virtual Account</b>\n"
        f"Starting Capital: ${snap['starting_capital']}\n"
        f"Cash Balance: ${snap['cash_balance']}\n"
        f"Unrealized P&L: ${snap['unrealized_pnl']}\n"
        f"Realized P&L: ${snap['realized_pnl']}\n"
        f"Total Equity: ${snap['total_equity']}\n"
        f"Open Virtual Positions: {len(snap['open_positions'])}\n\n"
        f"<b>Trading Windows</b>\n"
        f"Morning Macro: {tw['morning_macro_window']}\n"
        f"US Options Window: {tw['us_options_window_dubai']}\n"
        f"Can Open New Option Trade: {tw['can_open_new_option_trade']}\n\n"
        f"<b>Today So Far</b>\n"
        f"Trades Logged: {stats['total']}\n"
        f"Pending Approval: {stats['pending']}\n"
        f"Virtual Open: {stats['virtual_open']}\n\n"
        f"Today is <b>Day 1</b> of the 7-day virtual production trial."
    )

def build_end_of_day_summary():
    snap = virtual_account_snapshot()
    stats = today_trade_stats()

    return (
        f"<b>End of Day Summary — Virtual Production</b>\n\n"
        f"Date: {today_dxb()}\n\n"
        f"<b>Trades</b>\n"
        f"Logged Today: {stats['total']}\n"
        f"Pending Approval: {stats['pending']}\n"
        f"Approved: {stats['approved']}\n"
        f"Rejected: {stats['rejected']}\n"
        f"Watch Only: {stats['watch_only']}\n"
        f"Blocked: {stats['blocked']}\n"
        f"Virtual Open: {stats['virtual_open']}\n"
        f"Virtual Stale Blocked: {stats['virtual_stale_blocked']}\n\n"
        f"<b>Virtual Account</b>\n"
        f"Cash Balance: ${snap['cash_balance']}\n"
        f"Unrealized P&L: ${snap['unrealized_pnl']}\n"
        f"Realized P&L: ${snap['realized_pnl']}\n"
        f"Total Equity: ${snap['total_equity']}\n"
        f"Open Virtual Positions: {len(snap['open_positions'])}"
    )
