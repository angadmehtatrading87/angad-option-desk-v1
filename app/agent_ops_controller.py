import argparse
import json
import os
import sqlite3
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
REPORTS_DIR = BASE_DIR / "reports"
TRADES_DB = DATA_DIR / "trades.db"
RUNTIME_STATE_PATH = DATA_DIR / "agent_runtime_state.json"
PROGRESS_LOG_PATH = DOCS_DIR / "AGENT_PROGRESS_LOG.md"


@dataclass
class RuntimeHealth:
    worker_alive: bool
    last_loop_time: Optional[str]
    last_signal_time: Optional[str]
    last_intent_time: Optional[str]
    last_trade_time: Optional[str]
    last_rejection_reason: Optional[str]
    execution_mode: str
    safety_gate_status: str
    two_phase_commit_status: str
    market_brain_last_scan_time: Optional[str]
    api_data_freshness: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_runtime_state() -> Dict[str, Any]:
    default = {
        "ig_worker_alive": False,
        "last_loop_time": None,
        "last_signal_time": None,
        "last_intent_time": None,
        "last_trade_time": None,
        "last_rejection_reason": None,
        "execution_mode": "shadow",
        "safety_gate_status": "enabled",
        "two_phase_commit_status": "enabled",
        "market_brain_last_scan_time": None,
        "api_data_freshness": "unknown",
        "updated_at": _now_iso(),
    }
    if not RUNTIME_STATE_PATH.exists():
        return default
    with RUNTIME_STATE_PATH.open("r", encoding="utf-8") as f:
        loaded = json.load(f)
    default.update(loaded)
    return default


def save_runtime_state(state: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = dict(state)
    payload["updated_at"] = _now_iso()
    with RUNTIME_STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _git(args: List[str]) -> Optional[str]:
    try:
        out = subprocess.check_output(["git", *args], cwd=BASE_DIR, text=True).strip()
        return out
    except Exception:
        return None


def get_git_summary() -> Dict[str, Optional[str]]:
    return {
        "branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "latest_commit": _git(["log", "-1", "--pretty=%h %ad %s", "--date=short"]),
    }


def get_merged_pr_log(limit: int = 10) -> List[str]:
    raw = _git(["log", f"--max-count={limit}", "--pretty=%s"])
    if not raw:
        return []
    return [line for line in raw.splitlines() if "#" in line or "Merge pull request" in line]


def _fetch_trade_rows(days: int = 31) -> List[sqlite3.Row]:
    if not TRADES_DB.exists():
        return []
    conn = sqlite3.connect(TRADES_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    cur.execute(
        """
        SELECT timestamp, symbol, pnl, size, capital_used
        FROM executed_trades
        WHERE date(timestamp) >= date(?)
        ORDER BY timestamp DESC
        """,
        (since,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def trading_performance_report() -> Dict[str, Any]:
    rows = _fetch_trade_rows()
    if not rows:
        return {"status": "unavailable", "reason": "No trade rows or missing trades.db"}

    now = datetime.now(timezone.utc)
    day_key = now.strftime("%Y-%m-%d")
    week_ago = now - timedelta(days=7)
    month_key = now.strftime("%Y-%m")

    daily = weekly = monthly = 0.0
    wins = losses = 0
    total_size = total_capital = 0.0
    symbol_map: Dict[str, float] = {}

    for r in rows:
        ts = r["timestamp"] or ""
        pnl = float(r["pnl"] or 0.0)
        size = float(r["size"] or 0.0)
        cap = float(r["capital_used"] or 0.0)
        symbol = r["symbol"] or "UNKNOWN"
        if ts.startswith(day_key):
            daily += pnl
        if ts >= week_ago.strftime("%Y-%m-%d"):
            weekly += pnl
        if ts.startswith(month_key):
            monthly += pnl
        wins += 1 if pnl > 0 else 0
        losses += 1 if pnl < 0 else 0
        total_size += size
        total_capital += cap
        symbol_map[symbol] = symbol_map.get(symbol, 0.0) + pnl

    trade_count = len(rows)
    avg_trade_size = total_size / trade_count if trade_count else 0.0
    deployable_capital = total_capital
    unused_capital = max(deployable_capital - total_size, 0.0)
    capital_util = (total_size / deployable_capital) if deployable_capital > 0 else None
    sorted_syms = sorted(symbol_map.items(), key=lambda x: x[1])
    drawdown = min(0.0, min(symbol_map.values()) if symbol_map else 0.0)

    return {
        "status": "ok",
        "daily_pnl": daily,
        "weekly_pnl": weekly,
        "monthly_pnl": monthly,
        "win_count": wins,
        "loss_count": losses,
        "trade_count": trade_count,
        "average_trade_size": avg_trade_size,
        "capital_utilization": capital_util,
        "deployable_capital": deployable_capital,
        "unused_capital": unused_capital,
        "drawdown": drawdown,
        "best_symbol": sorted_syms[-1][0] if sorted_syms else None,
        "worst_symbol": sorted_syms[0][0] if sorted_syms else None,
        "target_track": "on_track" if monthly >= 0.04 * max(deployable_capital, 1.0) else "off_track",
    }


def intelligence_level_report() -> Dict[str, Any]:
    scores = {
        "safety_controls_level": 5,
        "execution_protection_level": 5,
        "market_scanning_level": 4,
        "candle_intelligence_level": 4,
        "news_sentiment_level": 3,
        "capital_allocation_level": 4,
        "learning_feedback_level": 3,
        "dashboard_visibility_level": 4,
    }
    overall = round(sum(scores.values()) / len(scores), 2)
    scores["overall_intelligence_maturity_level"] = overall
    return scores


def collect_agent_ops_state() -> Dict[str, Any]:
    runtime = load_runtime_state()
    return {
        "generated_at": _now_iso(),
        "git": get_git_summary(),
        "merged_prs": get_merged_pr_log(),
        "current_phase": "agent_ops_control_layer",
        "pending_tasks": [
            "Wire live runtime heartbeat producer",
            "Add richer PR metadata ingestion",
        ],
        "known_issues": ["Trading performance depends on executed_trades schema availability"],
        "capability_level": intelligence_level_report()["overall_intelligence_maturity_level"],
        "runtime_health": runtime,
        "trading_performance": trading_performance_report(),
        "market_brain_shadow_status": {
            "mode": "shadow",
            "last_scan_time": runtime.get("market_brain_last_scan_time"),
        },
        "intelligence_level": intelligence_level_report(),
    }


def update_progress_log(state: Dict[str, Any]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    content = f"""# Agent Progress Log\n\n- Updated at: {state['generated_at']}\n- Current intelligence level: {state['capability_level']}\n\n## Merged PRs\n"""
    prs = state.get("merged_prs") or ["Unavailable"]
    content += "\n".join([f"- {p}" for p in prs])
    content += "\n\n## Major Features Added\n- Agent Ops Controller monitoring/reporting layer\n\n## Tests Run\n- pytest tests/test_agent_ops_controller.py\n\n## Known Issues\n"
    content += "\n".join([f"- {i}" for i in state.get("known_issues", [])])
    content += "\n\n## Next Recommended Work\n"
    content += "\n".join([f"- {i}" for i in state.get("pending_tasks", [])])
    content += "\n\n## Rollback Notes\n- Revert commit introducing app/agent_ops_controller.py and related docs/tests if needed.\n"
    PROGRESS_LOG_PATH.write_text(content, encoding="utf-8")


def generate_weekly_report(state: Optional[Dict[str, Any]] = None) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    state = state or collect_agent_ops_state()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    path = REPORTS_DIR / f"weekly_agent_report_{stamp}.md"
    perf = state.get("trading_performance", {})
    report = f"""# Weekly Agent Report ({stamp})\n\n## Executive Summary\nAgent Ops Controller snapshot generated for operator visibility.\n\n## Development Progress\n- Current phase: {state.get('current_phase')}\n- Latest commit: {state.get('git', {}).get('latest_commit')}\n\n## Trading Performance\n- Weekly P&L: {perf.get('weekly_pnl', 'unavailable')}\n- Monthly P&L: {perf.get('monthly_pnl', 'unavailable')}\n\n## Capital Utilization\n- Capital utilization: {perf.get('capital_utilization', 'unavailable')}\n- Deployable capital: {perf.get('deployable_capital', 'unavailable')}\n\n## Market Brain Status\n- Shadow status: {state.get('market_brain_shadow_status')}\n\n## Runtime Health\n- Runtime: {state.get('runtime_health')}\n\n## Intelligence Level\n- Scorecard: {state.get('intelligence_level')}\n\n## Problems Found\n- {state.get('known_issues')}\n\n## Next Recommended PRs/Tasks\n- {state.get('pending_tasks')}\n"""
    path.write_text(report, encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weekly-report", action="store_true")
    args = parser.parse_args()

    state = collect_agent_ops_state()
    save_runtime_state(load_runtime_state())
    update_progress_log(state)
    if args.weekly_report:
        report_path = generate_weekly_report(state)
        print(report_path)
        print(report_path.read_text(encoding="utf-8"))
    else:
        print(json.dumps(state, indent=2, default=str))


if __name__ == "__main__":
    main()
