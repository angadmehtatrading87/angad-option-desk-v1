import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

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


def _db_scalar(query: str):
    if not TRADES_DB.exists():
        return None
    try:
        conn = sqlite3.connect(TRADES_DB)
        cur = conn.cursor()
        cur.execute(query)
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def _table_exists(name: str) -> bool:
    return _db_scalar(f"SELECT count(*) FROM sqlite_master WHERE type='table' AND name='{name}'") == 1


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
        "market_brain_last_scan": rt.get("market_brain_last_scan_time"),
        "research_last_report": rt.get("research_latest_report_path") or rt.get("research_daily_report_path"),
        "agent_ops_last_report": rt.get("agent_ops_latest_weekly_report_path"),
        "last_scan": rt.get("last_scan_time") or rt.get("market_brain_last_scan_time"),
        "last_trade": rt.get("last_trade_time"),
        "last_rejection": rt.get("last_rejection_reason") or rt.get("ig_execution_worker_last_rejection_reason"),
        "last_error": rt.get("last_error"),
        "market_brain_execution_enabled": rt.get("market_brain_execution_enabled", False),
        "market_brain_execution_mode": rt.get("market_brain_execution_mode", "demo"),
        "market_brain_last_trade_candidate": rt.get("market_brain_last_trade_candidate"),
        "market_brain_last_executed_trade": rt.get("market_brain_last_executed_trade"),
        "market_brain_last_rejection_reason": rt.get("market_brain_last_rejection_reason"),
        "capital_utilization": rt.get("capital_utilization", {}),
    }


def get_performance() -> dict:
    perf = {}
    if _table_exists("virtual_equity_log"):
        perf["daily_pnl"] = _db_scalar("SELECT pnl FROM virtual_equity_log ORDER BY id DESC LIMIT 1")
    else:
        perf["daily_pnl"] = None
    perf.update({"weekly_pnl": None, "monthly_pnl": None, "monthly_return_pct": None, "drawdown": None})
    perf["capital_used"] = _db_scalar("SELECT used_capital FROM virtual_account ORDER BY id DESC LIMIT 1") if _table_exists("virtual_account") else None
    perf["capital_unused"] = _db_scalar("SELECT available_capital FROM virtual_account ORDER BY id DESC LIMIT 1") if _table_exists("virtual_account") else None
    perf["objective_progress"] = None
    perf["best_symbol"] = None
    perf["worst_symbol"] = None
    return perf


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
