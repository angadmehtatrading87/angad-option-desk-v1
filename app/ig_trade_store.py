import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")
DXB = ZoneInfo("Asia/Dubai")

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _now():
    return datetime.now(DXB).isoformat()

def ensure_ig_tables():
    conn = _conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ig_trade_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        epic TEXT NOT NULL,
        market_name TEXT,
        action TEXT NOT NULL,
        confidence REAL,
        reason TEXT,
        direction TEXT,
        size REAL,
        stop_distance REAL,
        limit_distance REAL,
        status TEXT NOT NULL,
        deal_reference TEXT,
        deal_id TEXT,
        raw_response TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

def log_ig_decision(
    epic,
    market_name,
    action,
    confidence,
    reason,
    direction,
    size,
    stop_distance,
    limit_distance,
    status,
    deal_reference=None,
    deal_id=None,
    raw_response=None
):
    ensure_ig_tables()
    conn = _conn()
    cur = conn.cursor()
    now = _now()
    cur.execute("""
        INSERT INTO ig_trade_log (
            epic, market_name, action, confidence, reason, direction, size,
            stop_distance, limit_distance, status, deal_reference, deal_id,
            raw_response, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        epic, market_name, action, confidence, reason, direction, size,
        stop_distance, limit_distance, status, deal_reference, deal_id,
        raw_response, now, now
    ))
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id

def recent_ig_trade_log(limit=50):
    ensure_ig_tables()
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT *
        FROM ig_trade_log
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def open_ig_log_count():
    ensure_ig_tables()
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) AS cnt
        FROM ig_trade_log
        WHERE status IN ('SUBMITTING','CONFIRMED_IN_BOOK','ACCEPTED_NOT_VISIBLE_IN_BOOK','PENDING_CONFIRMATION')
    """)
    row = cur.fetchone()
    conn.close()
    return int(row["cnt"] or 0)

def mark_ig_log(row_id, status, deal_reference=None, deal_id=None, raw_response=None):
    ensure_ig_tables()
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE ig_trade_log
        SET status=?,
            deal_reference=COALESCE(?, deal_reference),
            deal_id=COALESCE(?, deal_id),
            raw_response=COALESCE(?, raw_response),
            updated_at=?
        WHERE id=?
    """, (
        status, deal_reference, deal_id, raw_response, _now(), row_id
    ))
    conn.commit()
    conn.close()
