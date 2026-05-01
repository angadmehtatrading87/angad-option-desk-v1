import sqlite3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import agent_ops_controller as ops


def _mk_db(path: Path, ddl: str, rows=None):
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute(ddl)
    for row in rows or []:
        cur.execute(*row)
    conn.commit()
    conn.close()


def test_runtime_state_serialization(tmp_path, monkeypatch):
    path = tmp_path / "agent_runtime_state.json"
    monkeypatch.setattr(ops, "RUNTIME_STATE_PATH", path)
    monkeypatch.setattr(ops, "DATA_DIR", tmp_path)
    ops.save_runtime_state({"ig_worker_alive": True, "execution_mode": "shadow"})
    data = ops.load_runtime_state()
    assert data["ig_worker_alive"] is True
    assert data["execution_mode"] == "shadow"


def test_intelligence_scorecard():
    score = ops.intelligence_level_report()
    assert score["safety_controls_level"] >= 1
    assert score["overall_intelligence_maturity_level"] > 0


def test_missing_db_file(monkeypatch, tmp_path):
    monkeypatch.setattr(ops, "TRADES_DB", tmp_path / "missing.db")
    rep = ops.trading_performance_report()
    assert rep["status"] == "unavailable"
    assert rep["reason"] == "no_data"


def test_db_exists_without_trade_table(monkeypatch, tmp_path):
    db = tmp_path / "trades.db"
    _mk_db(db, "CREATE TABLE something_else(id INTEGER PRIMARY KEY, x TEXT)")
    monkeypatch.setattr(ops, "TRADES_DB", db)
    rep = ops.trading_performance_report()
    assert rep["status"] == "unavailable"
    assert rep["source_table"] is None


def test_executed_trades_exists(monkeypatch, tmp_path):
    db = tmp_path / "trades.db"
    _mk_db(
        db,
        "CREATE TABLE executed_trades(timestamp TEXT, symbol TEXT, pnl REAL, size REAL, capital_used REAL)",
        rows=[(
            "INSERT INTO executed_trades(timestamp,symbol,pnl,size,capital_used) VALUES(?,?,?,?,?)",
            ("2026-05-01T00:00:00", "EURUSD", 25.0, 100.0, 1000.0),
        )],
    )
    monkeypatch.setattr(ops, "TRADES_DB", db)
    rep = ops.trading_performance_report()
    assert rep["status"] == "ok"
    assert rep["source_table"] == "executed_trades"


def test_fallback_table_exists(monkeypatch, tmp_path):
    db = tmp_path / "trades.db"
    _mk_db(
        db,
        "CREATE TABLE trades(timestamp TEXT, symbol TEXT, pnl REAL, size REAL, capital_used REAL)",
        rows=[(
            "INSERT INTO trades(timestamp,symbol,pnl,size,capital_used) VALUES(?,?,?,?,?)",
            ("2026-05-01T00:00:00", "GBPUSD", -5.0, 50.0, 500.0),
        )],
    )
    monkeypatch.setattr(ops, "TRADES_DB", db)
    rep = ops.trading_performance_report()
    assert rep["status"] == "ok"
    assert rep["source_table"] == "trades"


def test_weekly_report_creation(tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(ops, "TRADES_DB", tmp_path / "missing.db")
    state = ops.collect_agent_ops_state()
    report_path = ops.generate_weekly_report(state)
    assert report_path.exists()
    assert "Weekly Agent Report" in report_path.read_text(encoding="utf-8")


def test_dashboard_state_integration():
    content = Path("app/dashboard_state.py").read_text(encoding="utf-8")
    assert '"agent_ops"' in content
    assert 'collect_agent_ops_state' in content
