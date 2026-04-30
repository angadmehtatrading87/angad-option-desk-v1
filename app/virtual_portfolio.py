import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from app.quote_engine import quote_options

DXB = ZoneInfo("Asia/Dubai")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_schema():
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE virtual_positions ADD COLUMN quantity INTEGER DEFAULT 1")
    except Exception:
        pass
    conn.commit()
    conn.close()

def _now():
    return datetime.now(DXB).isoformat()

def _get_trade(trade_id):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM trade_proposals WHERE id=?", (trade_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def _parse_legs(legs):
    parts = [x.strip() for x in str(legs or "").split("/")]
    if len(parts) != 2:
        return None
    left = parts[0].split()
    right = parts[1].split()
    if len(left) < 2 or len(right) < 2:
        return None
    return {
        "left_action": left[0].lower(),
        "left_symbol": left[1],
        "right_action": right[0].lower(),
        "right_symbol": right[1],
    }

def current_unit_spread_mid(legs, strategy):
    parsed = _parse_legs(legs)
    if not parsed:
        return None, "BAD_LEGS"

    syms = [parsed["left_symbol"], parsed["right_symbol"]]
    quotes = quote_options(syms)

    def mid(q):
        if not q:
            return None
        bid = q.get("bid")
        ask = q.get("ask")
        if bid is None or ask is None:
            return None
        return (float(bid) + float(ask)) / 2

    lq = quotes.get(parsed["left_symbol"])
    rq = quotes.get(parsed["right_symbol"])
    lm = mid(lq)
    rm = mid(rq)

    if lm is None or rm is None:
        return None, "QUOTE_MISSING"

    strat = str(strategy or "").lower()
    if strat == "debit_spread":
        if parsed["left_action"] == "buy" and parsed["right_action"] == "sell":
            return round(lm - rm, 4), "OK"
        if parsed["left_action"] == "sell" and parsed["right_action"] == "buy":
            return round(rm - lm, 4), "OK"

    if strat == "put_credit_spread":
        if parsed["left_action"] == "sell" and parsed["right_action"] == "buy":
            return round(lm - rm, 4), "OK"
        if parsed["left_action"] == "buy" and parsed["right_action"] == "sell":
            return round(rm - lm, 4), "OK"

    if parsed["left_action"] == "buy":
        return round(lm - rm, 4), "OK"
    return round(rm - lm, 4), "OK"

def log_equity(note=""):
    snap = virtual_account_snapshot()
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO virtual_equity_log (
            timestamp, cash_balance, unrealized_pnl, realized_pnl, total_equity, note
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        _now(),
        float(snap.get("cash_balance", 0) or 0),
        float(snap.get("unrealized_pnl", 0) or 0),
        float(snap.get("realized_pnl", 0) or 0),
        float(snap.get("total_equity", 0) or 0),
        note,
    ))
    conn.commit()
    conn.close()

def open_virtual_position(trade_id, quantity=1):
    ensure_schema()
    trade = _get_trade(trade_id)
    if not trade:
        raise ValueError(f"Trade {trade_id} not found")

    qty = int(quantity or 1)
    if qty < 1:
        raise ValueError("Quantity must be >= 1")

    conn = _conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM virtual_account WHERE id=1")
    acct = cur.fetchone()
    if not acct:
        raise ValueError("virtual_account row missing")

    unit_risk = float(trade.get("max_risk") or 0)
    reserved_capital = unit_risk * qty
    current_cash = float(acct["cash_balance"] or 0)

    if current_cash < reserved_capital:
        raise ValueError(f"Insufficient virtual cash for reserved capital {reserved_capital}")

    cur.execute("""
        INSERT INTO virtual_positions (
            trade_id, symbol, strategy, expiry, legs, entry_debit, entry_credit,
            status, opened_at, notes, quantity
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?)
    """, (
        trade_id,
        trade.get("symbol"),
        trade.get("strategy"),
        trade.get("expiry"),
        trade.get("legs"),
        trade.get("estimated_debit"),
        trade.get("estimated_credit"),
        _now(),
        f"Virtual fill opened. quantity={qty}",
        qty
    ))

    cur.execute("""
        UPDATE virtual_account
        SET cash_balance = ?, updated_at = ?
        WHERE id=1
    """, (current_cash - reserved_capital, _now()))

    conn.commit()
    conn.close()

    log_equity(note=f"Opened virtual position from trade #{trade_id} qty={qty}")
    return {"trade_id": trade_id, "quantity": qty, "reserved_capital": reserved_capital}

def list_open_virtual_positions():
    ensure_schema()
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM virtual_positions
        WHERE status='OPEN'
        ORDER BY id DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def close_virtual_position(position_id, exit_price, note=""):
    ensure_schema()
    conn = _conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM virtual_positions WHERE id=?", (position_id,))
    pos = cur.fetchone()
    if not pos:
        conn.close()
        raise ValueError(f"Position {position_id} not found")
    pos = dict(pos)

    cur.execute("SELECT * FROM trade_proposals WHERE id=?", (pos["trade_id"],))
    trade = cur.fetchone()
    if not trade:
        conn.close()
        raise ValueError(f"Trade {pos['trade_id']} not found")
    trade = dict(trade)

    cur.execute("SELECT * FROM virtual_account WHERE id=1")
    acct = cur.fetchone()
    acct = dict(acct)

    qty = int(pos.get("quantity") or 1)
    unit_risk = float(trade.get("max_risk") or 0)
    reserved_capital = unit_risk * qty

    exit_px = float(exit_price or 0)
    entry_debit = pos.get("entry_debit")
    entry_credit = pos.get("entry_credit")
    strategy = str(pos.get("strategy") or "").lower()

    if strategy == "debit_spread":
        entry_unit = float(entry_debit or 0)
        realized = round((exit_px - entry_unit) * 100 * qty, 2)
    else:
        entry_unit = float(entry_credit or 0)
        realized = round((entry_unit - exit_px) * 100 * qty, 2)

    new_cash = float(acct.get("cash_balance") or 0) + reserved_capital + realized

    cur.execute("""
        UPDATE virtual_positions
        SET status='CLOSED',
            closed_at=?,
            exit_price=?,
            realized_pnl=?,
            notes=?
        WHERE id=?
    """, (
        _now(),
        exit_px,
        realized,
        note,
        position_id
    ))

    cur.execute("""
        UPDATE virtual_account
        SET cash_balance=?, updated_at=?
        WHERE id=1
    """, (new_cash, _now()))

    conn.commit()
    conn.close()

    log_equity(note=f"Closed virtual position #{position_id}")
    return {"position_id": position_id, "realized_pnl": realized, "reserved_capital": reserved_capital}

def virtual_account_snapshot():
    ensure_schema()
    conn = _conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM virtual_account WHERE id=1")
    acct = cur.fetchone()
    acct = dict(acct) if acct else {"starting_capital": 0.0, "cash_balance": 0.0}

    cur.execute("SELECT * FROM virtual_positions WHERE status='OPEN' ORDER BY id DESC")
    open_positions = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT COALESCE(SUM(realized_pnl),0) AS realized FROM virtual_positions WHERE status='CLOSED'")
    realized_pnl = float(cur.fetchone()["realized"] or 0)

    unrealized_details = []
    total_unrealized = 0.0
    total_reserved = 0.0

    for pos in open_positions:
        trade = _get_trade(pos["trade_id"])
        qty = int(pos.get("quantity") or 1)
        unit_mid, quote_status = current_unit_spread_mid(pos.get("legs"), pos.get("strategy"))
        unit_risk = float(trade.get("max_risk") or 0)
        reserved = unit_risk * qty
        total_reserved += reserved

        if str(pos.get("strategy") or "").lower() == "debit_spread":
            entry_unit = float(pos.get("entry_debit") or 0)
            unreal = None if unit_mid is None else round((unit_mid - entry_unit) * 100 * qty, 2)
            entry_price = entry_unit
        else:
            entry_unit = float(pos.get("entry_credit") or 0)
            unreal = None if unit_mid is None else round((entry_unit - unit_mid) * 100 * qty, 2)
            entry_price = entry_unit

        if unreal is not None:
            total_unrealized += unreal

        pos["quantity"] = qty
        pos["reserved_capital"] = reserved

        unrealized_details.append({
            "position_id": pos["id"],
            "trade_id": pos["trade_id"],
            "symbol": pos["symbol"],
            "strategy": pos["strategy"],
            "quantity": qty,
            "entry_price": entry_price,
            "current_spread_mid": unit_mid,
            "quote_status": quote_status,
            "unrealized_pnl": unreal,
            "reserved_capital": reserved,
        })

    cash = float(acct.get("cash_balance") or 0)
    total_equity = round(cash + total_reserved + total_unrealized, 2)

    conn.close()

    return {
        "starting_capital": float(acct.get("starting_capital") or 0),
        "cash_balance": cash,
        "unrealized_pnl": round(total_unrealized, 2),
        "realized_pnl": round(realized_pnl, 2),
        "total_equity": total_equity,
        "open_positions": open_positions,
        "unrealized_details": unrealized_details,
    }
