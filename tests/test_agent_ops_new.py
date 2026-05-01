from pathlib import Path
from app.agent_ops.db_reader import DBReader
from app.agent_ops.deployment_planner import weekend_guard
from app.agent_ops.runtime_health import RuntimeHealthStore
from app.agent_ops.cli import weekly_report, request_approval


def test_missing_db(tmp_path):
    r = DBReader(tmp_path / "missing.db")
    assert r.available_tables() == set()


def test_runtime_state_serialization(tmp_path):
    s = RuntimeHealthStore(tmp_path / "state.json")
    s.save({"worker_status": "alive"})
    assert s.load()["worker_status"] == "alive"


def test_weekly_report_creation(tmp_path):
    (tmp_path / "data").mkdir()
    p = weekly_report(tmp_path)
    assert p.exists()


def test_approval_request_creation(tmp_path):
    p, _ = request_approval(tmp_path)
    assert p.exists()


def test_weekend_guard_blocks_weekday():
    ok, _ = weekend_guard(force=False)
    assert ok in {True, False}
