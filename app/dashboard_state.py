import os
import sqlite3
from app.market_prep_brain import load_market_prep_state
from app.virtual_portfolio import virtual_account_snapshot
from app.learning_engine import recent_learning
from app.ig_api_governor import get_ig_cached_snapshot
from app.market_brain import MarketBrainInput, run_market_brain
from app.market_brain.adapters import IGAdapter
from app.agent_ops_controller import collect_agent_ops_state

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
    agent_ops = collect_agent_ops_state()

    return {
        "last_run_dxb": exec_state.get("last_run_dxb"),
        "selection_result": exec_state.get("selection_result", {}),
        "entry_results": exec_state.get("entry_results", []),
    }



def _build_market_brain_state():
    snap = get_ig_cached_snapshot(force_refresh=False) or {}
    adapter = IGAdapter(snapshot=snap)
    watchlist = adapter.get_watchlist()
    account = adapter.get_account()
    positions = adapter.get_positions()
    candles = adapter.get_candles([m.get("epic") for m in watchlist if m.get("epic")])
    monthly = {"month_start_capital": account.get("balance", 0.0), "trading_days_remaining": 10}
    out = run_market_brain(MarketBrainInput(watchlist=watchlist, candles=candles, account=account, positions=positions, monthly=monthly))
    return out.to_dict()

def get_dashboard_state():
    market = load_market_prep_state()
    portfolio = virtual_account_snapshot()
    learning = recent_learning(8)
    reporting = load_reporting_state()
    curve = equity_curve(40)
    execution = execution_log_snapshot()
    market_brain = _build_market_brain_state()

    return {
        "market": market,
        "portfolio": portfolio,
        "learning": learning,
        "reporting": reporting,
        "curve": curve,
        "execution": execution,
        "market_brain": market_brain,
        "agent_ops": {
            "current_phase": agent_ops.get("current_phase"),
            "intelligence_level": agent_ops.get("capability_level"),
            "runtime_health": agent_ops.get("runtime_health"),
            "latest_merged_features": agent_ops.get("merged_prs", [])[:3],
            "weekly_pnl": agent_ops.get("trading_performance", {}).get("weekly_pnl"),
            "monthly_target_progress": agent_ops.get("trading_performance", {}).get("target_track"),
            "pending_next_tasks": agent_ops.get("pending_tasks", []),
        },
    }
