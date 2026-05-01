from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agent_ops.controller import AgentOpsController
from app.agent_ops.db_reader import DBReader
from app.agent_ops.intelligence_report import LEVELS, generate as intelligence_generate
from app.agent_ops.runtime_health import RuntimeHealthStore
from app.agent_ops.trading_report import generate as trading_generate

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
RUNTIME_STATE_PATH = DATA_DIR / "agent_runtime_state.json"


def _runtime_store() -> RuntimeHealthStore:
    return RuntimeHealthStore(RUNTIME_STATE_PATH)


def load_runtime_state() -> dict[str, Any]:
    return _runtime_store().load()


def save_runtime_state(state: dict[str, Any]) -> dict[str, Any]:
    return _runtime_store().save(state)


def _build_db_reader() -> DBReader:
    return DBReader(DATA_DIR / "trades.db")


def _fetch_trade_rows(days: int = 31) -> list[dict[str, Any]]:
    # Compatibility helper retained for legacy tests and callers.
    # `days` is intentionally ignored because current schema/reporting reads full table.
    result = _build_db_reader().query(
        "ig_trade_log",
        "SELECT epic, status, size, created_at FROM ig_trade_log ORDER BY created_at DESC",
    )
    return result.get("rows", []) if result.get("status") == "ok" else []


def trading_performance_report() -> dict[str, Any]:
    rows = _fetch_trade_rows()
    if not rows:
        return {"status": "unavailable"}
    return trading_generate(_build_db_reader())


def intelligence_level_report() -> dict[str, Any]:
    runtime = load_runtime_state()
    report = intelligence_generate(runtime)
    level = int(report.get("intelligence_maturity_level", 0) or 0)
    return {
        "overall_intelligence_maturity_level": level,
        "overall_intelligence_maturity_label": LEVELS.get(level, "unknown"),
        "safety_controls_level": 2,
        "execution_mode": runtime.get("execution_mode", "shadow"),
    }


def collect_agent_ops_state() -> dict[str, Any]:
    return AgentOpsController(BASE_DIR).collect()


def generate_weekly_report(state: dict[str, Any]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = REPORTS_DIR / f"weekly_agent_report_{stamp}.md"
    content = f"""# Weekly Agent Report

## Trading Performance
{state.get('trading_performance')}

## Runtime Health
{state.get('runtime_health')}

## Market Brain Intelligence Status
{state.get('market_brain')}
"""
    out.write_text(content, encoding="utf-8")
    return out


__all__ = [
    "BASE_DIR",
    "DATA_DIR",
    "REPORTS_DIR",
    "RUNTIME_STATE_PATH",
    "collect_agent_ops_state",
    "generate_weekly_report",
    "intelligence_level_report",
    "load_runtime_state",
    "save_runtime_state",
    "trading_performance_report",
    "_fetch_trade_rows",
]
