import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNTIME_STATE = Path("data/agent_runtime_state.json")
TRADES_DB = Path("data/trades.db")
REPORTS_DIR = Path("reports")
SYSTEMD_UNITS = {
    "ig_execution_worker": "ig-execution-worker.service",
    "telegram_control_room": "telegram-control-room.service",
    "agent_ops_weekly_report": "agent-ops-weekly-report.timer",
    "agent_ops_weekend_approval": "agent-ops-weekend-approval.timer",
    "research_daily": "research-daily.timer",
    "research_weekly": "research-weekly.timer",
}


def _safe_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _service_status(unit: str) -> str:
    try:
        out = subprocess.check_output(["systemctl", "is-active", unit], text=True).strip()
        return out or "unknown"
    except Exception:
        return "unavailable"


def _systemd_statuses() -> dict:
    return {k: _service_status(v) for k, v in SYSTEMD_UNITS.items()}


def _git(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *cmd], text=True).strip()
    except Exception:
        return "unavailable"


def _db_conn():
    if not TRADES_DB.exists():
        return None
    try:
        return sqlite3.connect(TRADES_DB)
    except Exception:
        return None


def _table_exists(name: str) -> bool:
    conn = _db_conn()
    if conn is None:
        return False
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?", (name,))
        row = cur.fetchone()
        return bool(row and row[0] == 1)
    except Exception:
        return False
    finally:
        conn.close()


def _fetchone(query: str, params: tuple[Any, ...] = ()):
    conn = _db_conn()
    if conn is None:
        return None
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        return cur.fetchone()
    except Exception:
        return None
    finally:
        conn.close()


def _count_today(table: str, ts_col: str) -> int | None:
    if not _table_exists(table):
        return None
    row = _fetchone(
        f"SELECT COUNT(*) FROM {table} WHERE date({ts_col}) = date('now')"
    )
    return int(row[0]) if row and row[0] is not None else 0


def get_status() -> dict:
    state_missing = not RUNTIME_STATE.exists()
    rt = _safe_json(RUNTIME_STATE)
    if state_missing:
        rt = {
            "state": "state_file_missing",
            "execution_mode": "shadow",
            "kill_switch": False,
            "worker_status": "state_file_missing",
        }
    systemd = _systemd_statuses()
    return {
        "server_alive": True,
        "git_branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "git_commit": _git(["rev-parse", "--short", "HEAD"]),
        "worker": rt.get("worker_status", "state_file_missing" if state_missing else "unavailable"),
        "execution_mode": rt.get("execution_mode", "unknown"),
        "kill_switch": rt.get("kill_switch", False),
        "state": rt.get("state", "ok"),
        "ig_worker": systemd.get("ig_execution_worker", "unavailable"),
        "telegram_control_room": systemd.get("telegram_control_room", "unavailable"),
        "agent_ops_weekly_report": systemd.get("agent_ops_weekly_report", "unavailable"),
        "agent_ops_weekend_approval": systemd.get("agent_ops_weekend_approval", "unavailable"),
        "research_daily": systemd.get("research_daily", "unavailable"),
        "research_weekly": systemd.get("research_weekly", "unavailable"),
        "last_scan": rt.get("last_scan_time") or rt.get("market_brain_last_scan_time"),
        "last_trade": rt.get("last_trade_time"),
        "last_rejection": rt.get("last_rejection_reason") or rt.get("ig_execution_worker_last_rejection_reason"),
        "last_error": rt.get("last_error"),
        "market_brain_execution_enabled": rt.get("market_brain_execution_enabled", False),
        "capital_utilization": rt.get("capital_utilization", {}),
    }


def get_performance() -> dict:
    if not _table_exists("virtual_equity_log"):
        return {"unavailable_reason": "virtual_equity_log has no rows or table is missing"}
    eq = _fetchone(
        "SELECT realized_pnl, unrealized_pnl, total_equity, created_at FROM virtual_equity_log ORDER BY created_at DESC, id DESC LIMIT 1"
    )
    acct = _fetchone("SELECT cash_balance, starting_capital FROM virtual_account ORDER BY id DESC LIMIT 1") if _table_exists("virtual_account") else None
    trades = _fetchone("SELECT COUNT(*) FROM ig_trade_log") if _table_exists("ig_trade_log") else None
    open_pos = _fetchone("SELECT COUNT(*) FROM virtual_positions WHERE lower(COALESCE(status,'')) = 'open'") if _table_exists("virtual_positions") else None
    closed_pos = _fetchone("SELECT COUNT(*) FROM virtual_positions WHERE lower(COALESCE(status,'')) = 'closed'") if _table_exists("virtual_positions") else None
    feedback = _fetchone("SELECT outcome, feedback FROM learning_log ORDER BY id DESC LIMIT 1") if _table_exists("learning_log") else None
    return {
        "realized_pnl": eq[0] if eq else None,
        "unrealized_pnl": eq[1] if eq else None,
        "total_equity": eq[2] if eq else None,
        "equity_timestamp": eq[3] if eq else None,
        "cash_balance": acct[0] if acct else None,
        "starting_capital": acct[1] if acct else None,
        "trade_count": trades[0] if trades else None,
        "open_positions": open_pos[0] if open_pos else None,
        "closed_positions": closed_pos[0] if closed_pos else None,
        "latest_learning_outcome": feedback[0] if feedback else None,
        "latest_learning_feedback": feedback[1] if feedback else None,
    }


def get_trades_today() -> dict:
    if not _table_exists("ig_trade_log"):
        return {"unavailable_reason": "ig_trade_log table is missing"}
    count = _count_today("ig_trade_log", "created_at")
    latest = _fetchone("SELECT COALESCE(symbol, epic), action, confidence, status, reason FROM ig_trade_log ORDER BY created_at DESC, id DESC LIMIT 1")
    return {
        "today_trade_count": count,
        "latest_symbol_or_epic": latest[0] if latest else None,
        "latest_action": latest[1] if latest else None,
        "latest_confidence": latest[2] if latest else None,
        "latest_status": latest[3] if latest else None,
        "latest_reason": latest[4] if latest else None,
    }


def get_positions() -> dict:
    if not _table_exists("virtual_positions"):
        return {"unavailable_reason": "virtual_positions table is missing"}
    open_count = _fetchone("SELECT COUNT(*) FROM virtual_positions WHERE lower(COALESCE(status,'')) = 'open'")
    latest = _fetchone("SELECT symbol, epic, action, size, status, realized_pnl FROM virtual_positions WHERE lower(COALESCE(status,'')) = 'open' ORDER BY id DESC LIMIT 1")
    return {
        "open_positions": open_count[0] if open_count else 0,
        "latest_open_symbol": latest[0] if latest else None,
        "latest_open_epic": latest[1] if latest else None,
        "latest_open_action": latest[2] if latest else None,
        "latest_open_size": latest[3] if latest else None,
        "latest_open_status": latest[4] if latest else None,
        "latest_open_realized_pnl": latest[5] if latest else None,
    }


def get_capital() -> dict:
    if not _table_exists("virtual_account"):
        return {"unavailable_reason": "virtual_account table is missing"}
    acct = _fetchone("SELECT starting_capital, cash_balance FROM virtual_account ORDER BY id DESC LIMIT 1")
    eq = _fetchone("SELECT realized_pnl, unrealized_pnl, total_equity FROM virtual_equity_log ORDER BY id DESC LIMIT 1") if _table_exists("virtual_equity_log") else None
    utilization = None
    if acct and eq and acct[0]:
        utilization = round((eq[2] / acct[0]) * 100.0, 2) if eq[2] is not None else None
    return {
        "starting_capital": acct[0] if acct else None,
        "cash_balance": acct[1] if acct else None,
        "realized_pnl": eq[0] if eq else None,
        "unrealized_pnl": eq[1] if eq else None,
        "total_equity": eq[2] if eq else None,
        "capital_utilization_pct": utilization,
    }


def get_risk() -> dict:
    rt = _safe_json(RUNTIME_STATE)
    open_exposure = _fetchone("SELECT SUM(ABS(COALESCE(size, 0))) FROM virtual_positions WHERE lower(COALESCE(status,''))='open'") if _table_exists("virtual_positions") else None
    return {
        "kill_switch": rt.get("kill_switch", False),
        "execution_mode": rt.get("execution_mode", "unknown"),
        "reserve_rule": rt.get("reserve_rule") or "unavailable: reserve_rule missing in runtime state",
        "open_exposure": open_exposure[0] if open_exposure else None,
        "last_risk_block_reason": rt.get("last_risk_block_reason") or rt.get("ig_execution_worker_last_rejection_reason"),
    }


def get_why_no_trade() -> dict:
    rt = _safe_json(RUNTIME_STATE)
    return {
        "worker_status": rt.get("worker_status", "state_file_missing"),
        "last_decision_count": rt.get("decision_count", "unavailable: decision_count missing in runtime state"),
        "last_skip_reason": rt.get("last_skip_reason", "unavailable: last_skip_reason missing in runtime state"),
        "portfolio_block_reason": rt.get("portfolio_block_reason", "unavailable: portfolio_block_reason missing in runtime state"),
        "api_error": rt.get("last_error") or rt.get("api_timeout_error") or "none",
    }


def get_github_report() -> dict:
    return {
        "branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "commit": _git(["rev-parse", "--short", "HEAD"]),
        "merged_prs": _git(["log", "--oneline", "--merges", "-n", "5"]),
        "modified_files": _git(["status", "--short"]),
        "pending_deploy": "pending" if (REPORTS_DIR / "latest_deployment_approval.md").exists() else "none",
    }


def get_approval() -> dict:
    p = REPORTS_DIR / "latest_deployment_approval.md"
    return {"pending": p.exists(), "path": str(p), "text": p.read_text()[:2000] if p.exists() else ""}


def append_runtime_event(event: dict):
    state = _safe_json(RUNTIME_STATE)
    events = state.get("events", [])
    events.append({"timestamp": datetime.now(timezone.utc).isoformat(), **event})
    state["events"] = events[-200:]
    RUNTIME_STATE.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_STATE.write_text(json.dumps(state, indent=2))


def update_runtime(fields: dict):
    state = _safe_json(RUNTIME_STATE)
    state.update(fields)
    RUNTIME_STATE.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_STATE.write_text(json.dumps(state, indent=2))
