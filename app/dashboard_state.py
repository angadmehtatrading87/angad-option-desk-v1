import os
import sqlite3
from app.market_prep_brain import load_market_prep_state
from app.virtual_portfolio import virtual_account_snapshot
from app.learning_engine import recent_learning

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")
REPORTING_STATE = os.path.join(BASE_DIR, "data", "reporting_state.json")

def load_reporting_state():
    import json
    if not os.path.exists(REPORTING_STATE):
        return {"withdrawal_pool": 0.0}
    with open(REPORTING_STATE, "r") as f:
        return json.load(f)

def equity_curve(limit=30):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT timestamp, cash_balance, unrealized_pnl, realized_pnl, total_equity, note
        FROM virtual_equity_log
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    rows.reverse()
    return rows

def execution_log_snapshot():
    market = load_market_prep_state()
    exec_state = market.get("execution_brain", {})
    return {
        "last_run_dxb": exec_state.get("last_run_dxb"),
        "selection_result": exec_state.get("selection_result", {}),
        "entry_results": exec_state.get("entry_results", []),
    }

def get_dashboard_state():
    market = load_market_prep_state()
    portfolio = virtual_account_snapshot()
    learning = recent_learning(8)
    reporting = load_reporting_state()
    curve = equity_curve(40)
    execution = execution_log_snapshot()

    return {
        "market": market,
        "portfolio": portfolio,
        "learning": learning,
        "reporting": reporting,
        "curve": curve,
        "execution": execution,
    }
