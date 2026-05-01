from app.telegram_control_room import status_provider as sp


def test_status_missing_runtime_state(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sp, "_git", lambda *_: "test")
    monkeypatch.setattr(sp, "_systemd_statuses", lambda: {"ig_execution_worker": "active"})
    out = sp.get_status()
    assert out["state"] == "state_file_missing"
    assert out["worker"] == "state_file_missing"


def test_status_present_runtime_state(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    sp.update_runtime({
        "worker_status": "alive",
        "execution_mode": "shadow",
        "market_brain_last_scan_time": "2026-05-01T00:00:00+00:00",
        "agent_ops_latest_weekly_report_path": "reports/weekly.md",
    })
    monkeypatch.setattr(sp, "_git", lambda *_: "test")
    monkeypatch.setattr(sp, "_systemd_statuses", lambda: {"ig_execution_worker": "active"})
    out = sp.get_status()
    assert out["state"] == "ok"
    assert out["worker"] == "alive"
    assert out["ig_worker"] == "active"


def test_service_status_parsing_active_and_unavailable(monkeypatch):
    monkeypatch.setattr(sp.subprocess, "check_output", lambda *args, **kwargs: "active\n")
    assert sp._service_status("ig-execution-worker.service") == "active"

    def _raise(*args, **kwargs):
        raise RuntimeError("no systemd")

    monkeypatch.setattr(sp.subprocess, "check_output", _raise)
    assert sp._service_status("ig-execution-worker.service") == "unavailable"
