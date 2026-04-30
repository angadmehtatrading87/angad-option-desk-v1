import os
import sqlite3
import time
from app.learning_engine import record_closed_trade_learning

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")

def fetch_recent_closed_positions():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM virtual_positions
        WHERE status = 'CLOSED'
        ORDER BY id DESC
        LIMIT 50
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def main():
    while True:
        try:
            closed = fetch_recent_closed_positions()
            for row in closed:
                record_closed_trade_learning(row)
            time.sleep(60)
        except Exception:
            time.sleep(60)

if __name__ == "__main__":
    main()
