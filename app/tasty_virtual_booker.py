import json
import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")
DXB = ZoneInfo("Asia/Dubai")

MAX_CONTRACTS_PER_TRADE = 5
MIN_CONTRACTS_PER_TRADE = 1
MAX_RISK_PER_TRADE_USD = 1500.0

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def _now():
    return datetime.now(DXB).isoformat()

def ensure_virtual_tables():
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasty_virtual_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_trade_id INTEGER,
            symbol TEXT,
            strategy TEXT,
            side TEXT,
            quantity INTEGER,
            entry_value REAL,
            mark_value REAL,
            max_risk_usd REAL,
            confidence REAL,
            quality_score REAL,
            status TEXT,
            entry_reason TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasty_virtual_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            position_id INTEGER,
            event_type TEXT,
            payload TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def sane_quantity(max_risk, estimated_debit, estimated_credit):
    debit = _safe_float(estimated_debit)
    credit = _safe_float(estimated_credit)
    risk = _safe_float(max_risk)

    unit_risk = debit * 100.0 if debit > 0 else max((1.0 - credit) * 100.0, risk, 50.0)
    if unit_risk <= 0:
        unit_risk = 50.0

    qty = int(MAX_RISK_PER_TRADE_USD // unit_risk)
    qty = max(MIN_CONTRACTS_PER_TRADE, qty)
    qty = min(MAX_CONTRACTS_PER_TRADE, qty)
    return qty

def open_virtual_position(candidate: dict):
    ensure_virtual_tables()

    incoming_qty = int(candidate.get("quantity", 0) or 0)
    if incoming_qty > 0:
        qty = max(MIN_CONTRACTS_PER_TRADE, min(MAX_CONTRACTS_PER_TRADE, incoming_qty))
    else:
        qty = sane_quantity(
            candidate.get("max_risk"),
            candidate.get("estimated_debit"),
            candidate.get("estimated_credit"),
        )

    entry_value = _safe_float(candidate.get("estimated_debit"))
    if entry_value <= 0:
        entry_value = _safe_float(candidate.get("estimated_credit"))
    if entry_value <= 0:
        entry_value = max(0.05, round(_safe_float(candidate.get("max_risk")) / 100.0, 2))

    side = "DEBIT" if _safe_float(candidate.get("estimated_debit")) > 0 else "CREDIT"
    max_risk_usd = round(entry_value * 100.0 * qty, 2) if side == "DEBIT" else round(_safe_float(candidate.get("max_risk", 0)) * qty, 2)

    conn = _conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO tasty_virtual_positions (
            source_trade_id, symbol, strategy, side, quantity, entry_value, mark_value,
            max_risk_usd, confidence, quality_score, status, entry_reason, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        candidate.get("trade_id"),
        candidate.get("symbol"),
        candidate.get("setup_name") or candidate.get("strategy"),
        side,
        qty,
        round(entry_value, 2),
        round(entry_value, 2),
        max_risk_usd,
        _safe_float(candidate.get("confidence")),
        _safe_float(candidate.get("quality_score")),
        "OPEN",
        candidate.get("agent_view") or "AUTONOMOUS_ENTRY",
        _now(),
        _now()
    ))
    position_id = cur.lastrowid

    cur.execute("""
        INSERT INTO tasty_virtual_events (
            position_id, event_type, payload, created_at
        ) VALUES (?, ?, ?, ?)
    """, (
        position_id,
        "OPEN",
        json.dumps(candidate),
        _now()
    ))

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "position_id": position_id,
        "symbol": candidate.get("symbol"),
        "strategy": candidate.get("setup_name") or candidate.get("strategy"),
        "quantity": qty,
        "entry_value": round(entry_value, 2),
        "max_risk_usd": max_risk_usd,
        "status": "OPEN"
    }

def list_open_virtual_positions():
    ensure_virtual_tables()
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT *
        FROM tasty_virtual_positions
        WHERE status = 'OPEN'
        ORDER BY id DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
