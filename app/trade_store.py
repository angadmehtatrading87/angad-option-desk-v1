import sqlite3
import os
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trade_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            symbol TEXT NOT NULL,
            strategy TEXT NOT NULL,
            expiry TEXT NOT NULL,
            legs TEXT NOT NULL,
            estimated_credit REAL,
            estimated_debit REAL,
            max_risk REAL NOT NULL,
            target_profit REAL,
            stop_loss REAL,
            status TEXT NOT NULL,
            reason TEXT NOT NULL,
            risk_result TEXT NOT NULL,
            agent_grade TEXT,
            agent_view TEXT,
            confidence_score REAL,
            decision_summary TEXT,
            decision_reasons_for TEXT,
            decision_reasons_against TEXT
        )
    """)
    conn.commit()
    conn.close()

def create_trade(
    symbol,
    strategy,
    expiry,
    legs,
    estimated_credit,
    estimated_debit,
    max_risk,
    target_profit,
    stop_loss,
    status,
    reason,
    risk_result,
    decision=None
):
    init_db()
    decision = decision or {}

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO trade_proposals (
            created_at, symbol, strategy, expiry, legs, estimated_credit, estimated_debit,
            max_risk, target_profit, stop_loss, status, reason, risk_result,
            agent_grade, agent_view, confidence_score, decision_summary,
            decision_reasons_for, decision_reasons_against
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now(timezone.utc).isoformat(),
        symbol,
        strategy,
        expiry,
        legs,
        estimated_credit,
        estimated_debit,
        max_risk,
        target_profit,
        stop_loss,
        status,
        reason,
        risk_result,
        decision.get("grade"),
        decision.get("agent_view"),
        decision.get("confidence_score"),
        decision.get("summary"),
        " | ".join(decision.get("reasons_for", [])),
        " | ".join(decision.get("reasons_against", []))
    ))
    conn.commit()
    trade_id = cur.lastrowid
    conn.close()
    return trade_id

def list_trades(limit=20):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM trade_proposals
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows

def update_trade_status(trade_id, status):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE trade_proposals
        SET status = ?
        WHERE id = ?
    """, (status, trade_id))
    conn.commit()
    conn.close()

def recent_similar_trade_exists(symbol, strategy, cooldown_minutes=180):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT created_at FROM trade_proposals
        WHERE symbol = ?
        AND strategy = ?
        ORDER BY id DESC
        LIMIT 1
    """, (symbol, strategy))

    row = cur.fetchone()
    conn.close()

    if not row:
        return False

    try:
        from datetime import timedelta
        created_at = datetime.fromisoformat(row["created_at"])
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        age = datetime.now(timezone.utc) - created_at
        return age < timedelta(minutes=cooldown_minutes)
    except Exception:
        return False

def get_trade(trade_id):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM trade_proposals WHERE id = ?", (trade_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def update_broker_preview(trade_id, preview_status, preview_response, order_payload):
    import json
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE trade_proposals
        SET broker_preview_status = ?,
            broker_preview_response = ?,
            order_payload = ?
        WHERE id = ?
    """, (
        preview_status,
        json.dumps(preview_response, default=str),
        json.dumps(order_payload, default=str),
        trade_id
    ))
    conn.commit()
    conn.close()

def update_manual_ticket(trade_id, ticket_status, ticket_text):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE trade_proposals
        SET manual_ticket_status = ?,
            manual_ticket_text = ?
        WHERE id = ?
    """, (ticket_status, ticket_text, trade_id))
    conn.commit()
    conn.close()

def mark_manual_executed(trade_id, notes=""):
    from datetime import datetime, timezone
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE trade_proposals
        SET manual_ticket_status = ?,
            manual_executed_at = ?,
            manual_execution_notes = ?
        WHERE id = ?
    """, (
        "MANUALLY_EXECUTED",
        datetime.now(timezone.utc).isoformat(),
        notes,
        trade_id
    ))
    conn.commit()
    conn.close()

def mark_manual_not_executed(trade_id, notes=""):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE trade_proposals
        SET manual_ticket_status = ?,
            manual_execution_notes = ?
        WHERE id = ?
    """, (
        "NOT_EXECUTED",
        notes,
        trade_id
    ))
    conn.commit()
    conn.close()
