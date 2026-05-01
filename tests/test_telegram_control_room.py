import json
from pathlib import Path
from app.telegram_control_room.bot import TelegramControlRoomBot


def test_unauthorized_chat_rejected(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_ID", "123")
    assert "Unauthorized" in TelegramControlRoomBot().handle_command("999", "/status")


def test_authorized_chat_accepted(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_ID", "123")
    out = TelegramControlRoomBot().handle_command("123", "/help")
    assert "not a trade approval terminal" in out


def test_status_command(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_ID", "1")
    out = TelegramControlRoomBot().handle_command("1", "/status")
    assert "Control Room Status" in out


def test_performance_missing_data(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_ID", "1")
    out = TelegramControlRoomBot().handle_command("1", "/performance")
    assert "unavailable" in out


def test_github_command(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_ID", "1")
    out = TelegramControlRoomBot().handle_command("1", "/github")
    assert "GitHub/Deployment" in out


def test_approval_and_approve_phrase(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_ID", "1")
    Path("reports").mkdir()
    Path("reports/latest_deployment_approval.md").write_text("pending")
    b = TelegramControlRoomBot()
    assert "Pending deployment approval" in b.handle_command("1", "/approval")
    assert "Exact confirmation" in b.handle_command("1", "/approve_deploy wrong")
    assert "approved" in b.handle_command("1", "/approve_deploy APPROVE WEEKEND DEPLOYMENT")


def test_kill_and_resume(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_ID", "1")
    b = TelegramControlRoomBot()
    assert "Exact confirmation" in b.handle_command("1", "/kill_switch bad")
    assert "activated" in b.handle_command("1", "/kill_switch CONFIRM EMERGENCY SHUTDOWN")
    state = json.loads(Path("data/agent_runtime_state.json").read_text())
    assert state["kill_switch"] is True
    assert "cleared" in b.handle_command("1", "/system_resume CONFIRM SYSTEM RESUME")
    state2 = json.loads(Path("data/agent_runtime_state.json").read_text())
    assert state2["kill_switch"] is False


def test_no_shell_or_secrets(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_ID", "1")
    out = TelegramControlRoomBot().handle_command("1", "/exec rm -rf /")
    assert "Unknown command" in out


def test_tasty_tables_ignored(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_ID", "1")
    out = TelegramControlRoomBot().handle_command("1", "/performance")
    assert "Performance" in out
