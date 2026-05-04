from pathlib import Path

from app.agent_ops.factory import db_schema_inspector, validate_systemd_units, write_factory_report
from app.telegram_control_room.bot import TelegramControlRoomBot


def test_systemd_units_include_execstart_install():
    out = validate_systemd_units(Path('.'))
    assert out
    assert all(v['has_execstart'] and v['has_install'] for v in out.values())


def test_missing_db_tables(tmp_path):
    result = db_schema_inspector(tmp_path / 'missing.db')
    assert result['exists'] is False
    assert 'ig_trade_log' in result['missing_tables']


def test_factory_report_generation(tmp_path):
    (tmp_path / 'deploy/systemd').mkdir(parents=True)
    (tmp_path / 'deploy/systemd/demo.service').write_text('[Unit]\n[Service]\nExecStart=/bin/true\n[Install]\nWantedBy=multi-user.target\n')
    (tmp_path / '.git').mkdir()
    out = write_factory_report(tmp_path)
    assert out.exists()


def test_new_telegram_commands(monkeypatch):
    monkeypatch.setenv('TELEGRAM_ALLOWED_CHAT_ID', '1')
    bot = TelegramControlRoomBot()
    assert 'positions' in bot.handle_command('1', '/positions')
    assert 'capital' in bot.handle_command('1', '/capital')
    assert 'risk' in bot.handle_command('1', '/risk')
    assert 'why_no_trade' in bot.handle_command('1', '/why_no_trade')
