import json
import os
import sqlite3
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ig_adapter import IGAdapter
from app.telegram_alerts import send_telegram_message

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")
POLICY_PATH = os.path.join(BASE_DIR, "config", "ig_risk_policy.json")
STATE_PATH = os.path.join(BASE_DIR, "data", "ig_reporter_state.json")
DXB = ZoneInfo("Asia/Dubai")

def load_policy():
    with open(POLICY_PATH, "r") as f:
        return json.load(f)

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def load_state():
    if not os.path.exists(STATE_PATH):
        return {"last_sent_at": None}
    with open(STATE_PATH, "r") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

def should_send(interval_hours):
    state = load_state()
    last = state.get("last_sent_at")
    if not last:
        return True
    try:
        prev = datetime.fromisoformat(last)
    except Exception:
        return True
    now = datetime.now(DXB)
    return (now - prev).total_seconds() >= interval_hours * 3600

def recent_ig_logs(limit=20):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, epic, market_name, direction, size, status, deal_reference, created_at
        FROM ig_trade_log
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def build_report():
    ig = IGAdapter()
    login = ig.login()
    if not login.get("ok"):
        return {
            "ok": False,
            "message": "IG report skipped: login failed."
        }

    positions = ig.positions()
    pos_body = positions.get("body") if isinstance(positions.get("body"), dict) else {}
    pos_list = pos_body.get("positions", []) if isinstance(pos_body, dict) else []

    acct = (login.get("body") or {}).get("accountInfo", {}) or {}
    balance = acct.get("balance", 0)
    profit_loss = acct.get("profitLoss", 0)
    available = acct.get("available", 0)
    account_id = (login.get("body") or {}).get("currentAccountId", "-")

    logs = recent_ig_logs(10)

    lines = [
        "<b>IG FX Desk Report</b>",
        "",
        f"Account: {account_id}",
        f"Balance: {balance}",
        f"Open P&L: {profit_loss}",
        f"Available: {available}",
        f"Open Positions: {len(pos_list)}",
        ""
    ]

    if pos_list:
        lines.append("<b>Open Positions</b>")
        for p in pos_list[:10]:
            market = p.get("market", {})
            position = p.get("position", {})
            lines.append(
                f"{market.get('instrumentName','-')} | {position.get('direction','-')} | "
                f"Size {position.get('size','-')} | Level {position.get('level','-')}"
            )
        lines.append("")

    if logs:
        lines.append("<b>Recent IG Executions</b>")
        for r in logs[:10]:
            lines.append(
                f"#{r.get('id')} {r.get('market_name') or r.get('epic')} | "
                f"{r.get('direction')} | {r.get('size')} | {r.get('status')}"
            )

    return {
        "ok": True,
        "message": "\n".join(lines)
    }

def main():
    while True:
        try:
            policy = load_policy()
            if not policy.get("enabled", False):
                time.sleep(300)
                continue

            interval_hours = int(policy.get("telegram_summary_interval_hours", 8))
            if should_send(interval_hours):
                report = build_report()
                if report.get("ok"):
                    send_telegram_message(report["message"])
                    save_state({"last_sent_at": datetime.now(DXB).isoformat()})
            time.sleep(300)
        except Exception:
            time.sleep(120)

if __name__ == "__main__":
    main()
