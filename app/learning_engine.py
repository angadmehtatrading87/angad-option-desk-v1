import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from app.market_prep_brain import load_market_prep_state

DXB = ZoneInfo("Asia/Dubai")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")

def init_learning_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS learning_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER,
            position_id INTEGER,
            symbol TEXT,
            strategy TEXT,
            regime TEXT,
            style TEXT,
            confidence REAL,
            entry_time TEXT,
            exit_time TEXT,
            realized_pnl REAL,
            exit_reason TEXT,
            quality_tags TEXT,
            mistake_tags TEXT,
            tomorrow_note TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def _jsonish_list(items):
    if not items:
        return ""
    return ", ".join([str(x) for x in items])

def infer_quality_and_mistake_tags(realized_pnl, exit_reason):
    quality_tags = []
    mistake_tags = []
    pnl = float(realized_pnl or 0)
    if pnl > 0:
        quality_tags.append("profitable")
    elif pnl < 0:
        mistake_tags.append("loss")
    else:
        quality_tags.append("flat")

    text = (exit_reason or "").lower()
    if "take_profit" in text:
        quality_tags.append("profit_taken")
    if "stop" in text:
        mistake_tags.append("stop_out")
    if "weakness" in text:
        mistake_tags.append("weak_entry_or_thesis_decay")
    if "reduce_risk" in text:
        quality_tags.append("risk_reduced")
    return quality_tags, mistake_tags

def tomorrow_adjustment_note(realized_pnl, regime, symbol):
    pnl = float(realized_pnl or 0)
    if pnl > 0:
        return f"Maintain or slightly favor similar high-quality {symbol} setups in {regime} if liquidity remains clean."
    if pnl < 0:
        return f"Tighten filters for {symbol} under {regime}; require stronger confirmation before entry."
    return f"No strong conclusion for {symbol}; keep selective."

def record_closed_trade_learning(position_row):
    init_learning_db()
    state = load_market_prep_state()
    regime_view = state.get("regime_view", {})
    regime = regime_view.get("regime", "UNKNOWN")
    style = regime_view.get("style", "unknown")
    confidence = regime_view.get("confidence", 0)

    trade_id = position_row.get("trade_id")
    position_id = position_row.get("id")
    symbol = position_row.get("symbol")
    strategy = position_row.get("strategy")
    entry_time = position_row.get("opened_at")
    exit_time = position_row.get("closed_at")
    realized_pnl = float(position_row.get("realized_pnl") or 0)
    exit_reason = position_row.get("notes") or ""

    quality_tags, mistake_tags = infer_quality_and_mistake_tags(realized_pnl, exit_reason)
    tomorrow_note = tomorrow_adjustment_note(realized_pnl, regime, symbol)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM learning_log WHERE position_id = ?", (position_id,))
    exists = cur.fetchone()
    if exists:
        conn.close()
        return {"status": "already_logged", "position_id": position_id}

    cur.execute("""
        INSERT INTO learning_log (
            trade_id, position_id, symbol, strategy, regime, style, confidence,
            entry_time, exit_time, realized_pnl, exit_reason,
            quality_tags, mistake_tags, tomorrow_note, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        trade_id, position_id, symbol, strategy, regime, style, confidence,
        entry_time, exit_time, realized_pnl, exit_reason,
        _jsonish_list(quality_tags), _jsonish_list(mistake_tags),
        tomorrow_note, datetime.now(DXB).isoformat()
    ))
    conn.commit()
    conn.close()
    return {
        "status": "logged",
        "position_id": position_id,
        "symbol": symbol,
        "realized_pnl": realized_pnl,
        "quality_tags": quality_tags,
        "mistake_tags": mistake_tags,
        "tomorrow_note": tomorrow_note,
    }

def recent_learning(limit=20):
    init_learning_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM learning_log ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
