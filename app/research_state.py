import os
import sqlite3

from app.market_prep_brain import load_market_prep_state
from app.exit_brain import evaluate_exit_decisions
from app.learning_engine import recent_learning
from app.virtual_portfolio import list_open_virtual_positions
from app.adaptive_learning import load_adaptation_state
from app.daily_objective_controller import compute_daily_objective_state

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def recent_trade_proposals(limit=150):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, symbol, strategy, expiry, status, max_risk,
               estimated_debit, estimated_credit, created_at, reason
        FROM trade_proposals
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def proposal_status_breakdown():
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT status, COUNT(*) as cnt
        FROM trade_proposals
        GROUP BY status
        ORDER BY cnt DESC, status
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def recent_execution_log(limit=50):
    state = load_market_prep_state()
    exec_state = state.get("execution_brain", {})
    return {
        "last_run_dxb": exec_state.get("last_run_dxb"),
        "selection_result": exec_state.get("selection_result", {}),
        "entry_results": exec_state.get("entry_results", [])[:limit],
    }

def get_research_state():
    market = load_market_prep_state()
    adaptation = load_adaptation_state()
    return {
        "market": market,
        "adaptation": adaptation,
        "daily_objective": compute_daily_objective_state(),
        "proposal_status_breakdown": proposal_status_breakdown(),
        "recent_trade_proposals": recent_trade_proposals(150),
        "execution": recent_execution_log(),
        "open_positions": list_open_virtual_positions(),
        "exit_decisions": evaluate_exit_decisions(),
        "learning": recent_learning(20),
    }
