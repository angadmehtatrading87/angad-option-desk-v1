import sqlite3
from pathlib import Path

from app.telegram_control_room.bot import TelegramControlRoomBot


def _seed_db(db_path: Path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE ig_trade_log (
            id INTEGER PRIMARY KEY,
            created_at TEXT,
            symbol TEXT,
            epic TEXT,
            action TEXT,
            confidence REAL,
            status TEXT,
            reason TEXT
        );
        CREATE TABLE virtual_equity_log (
            id INTEGER PRIMARY KEY,
            created_at TEXT,
            realized_pnl REAL,
            unrealized_pnl REAL,
            total_equity REAL
        );
        CREATE TABLE virtual_account (
            id INTEGER PRIMARY KEY,
            starting_capital REAL,
            cash_balance REAL
        );
        CREATE TABLE virtual_positions (
            id INTEGER PRIMARY KEY,
            symbol TEXT,
            epic TEXT,
            action TEXT,
            size REAL,
            status TEXT,
            realized_pnl REAL
        );
        CREATE TABLE trade_proposals (id INTEGER PRIMARY KEY, created_at TEXT);
        CREATE TABLE learning_log (
            id INTEGER PRIMARY KEY,
            outcome TEXT,
            feedback TEXT
        );
        """
    )
    cur.execute("INSERT INTO virtual_account(starting_capital, cash_balance) VALUES (100000, 75000)")
    cur.execute("INSERT INTO virtual_equity_log(created_at, realized_pnl, unrealized_pnl, total_equity) VALUES (datetime('now'), 1200, 300, 101500)")
    cur.execute("INSERT INTO ig_trade_log(created_at, symbol, epic, action, confidence, status, reason) VALUES (datetime('now'), 'AAPL', 'IX.D.AAPL', 'BUY', 0.85, 'submitted', 'breakout')")
    cur.execute("INSERT INTO virtual_positions(symbol, epic, action, size, status, realized_pnl) VALUES ('AAPL', 'IX.D.AAPL', 'BUY', 2, 'open', 0)")
    cur.execute("INSERT INTO learning_log(outcome, feedback) VALUES ('win', 'held conviction')")
    conn.commit()
    conn.close()


def test_wired_commands_read_actual_tables(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_ID", "1")
    Path("data").mkdir()
    _seed_db(Path("data/trades.db"))

    bot = TelegramControlRoomBot()
    assert "realized_pnl: 1200.0" in bot.handle_command("1", "/performance")
    assert "today_trade_count: 1" in bot.handle_command("1", "/trades_today")
    assert "open_positions: 1" in bot.handle_command("1", "/positions")
    assert "starting_capital: 100000.0" in bot.handle_command("1", "/capital")


def test_positions_no_open_positions_message(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_ID", "1")
    Path("data").mkdir()
    conn = sqlite3.connect("data/trades.db")
    conn.execute("CREATE TABLE virtual_positions (id INTEGER PRIMARY KEY, status TEXT)")
    conn.execute("INSERT INTO virtual_positions(status) VALUES ('closed')")
    conn.commit()
    conn.close()

    out = TelegramControlRoomBot().handle_command("1", "/positions")
    assert "no open positions" in out.lower()
