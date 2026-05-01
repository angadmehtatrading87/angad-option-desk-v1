import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))


from app import agent_ops_controller as ops


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


def test_report_generation_missing_data(monkeypatch):
    monkeypatch.setattr(ops, "_fetch_trade_rows", lambda days=31: [])
    rep = ops.trading_performance_report()
    assert rep["status"] == "unavailable"


def test_weekly_report_creation(tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "REPORTS_DIR", tmp_path)
    state = ops.collect_agent_ops_state()
    report_path = ops.generate_weekly_report(state)
    assert report_path.exists()
    assert "Weekly Agent Report" in report_path.read_text(encoding="utf-8")


def test_dashboard_state_integration():
    content = Path("app/dashboard_state.py").read_text(encoding="utf-8")
    assert '"agent_ops"' in content
    assert 'collect_agent_ops_state' in content
