import sqlite3
from pathlib import Path
from typing import Any

ACTIVE_TABLES={"ig_trade_log","virtual_equity_log","virtual_account","virtual_positions","trade_proposals","learning_log"}
# Tables that exist in legacy DBs but should be ignored by the agent reporting layer.
# Kept defensive — Tastytrade integration was removed but a deployed DB may still
# carry these tables for one or two upgrade cycles.
IGNORED_TABLES={"tasty_virtual_events","tasty_virtual_positions"}

class DBReader:
    def __init__(self, db_path: Path):
        self.db_path=Path(db_path)
    def _connect(self):
        if not self.db_path.exists():
            return None
        conn=sqlite3.connect(self.db_path)
        conn.row_factory=sqlite3.Row
        return conn
    def available_tables(self)->set[str]:
        conn=self._connect()
        if not conn:return set()
        rows=conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall();conn.close()
        return {r['name'] for r in rows if r['name'] in ACTIVE_TABLES}
    def query(self, table:str, sql:str, params:tuple[Any,...]=()):
        if table in IGNORED_TABLES or table not in self.available_tables():
            return {"status":"unavailable","rows":[]}
        conn=self._connect();
        rows=[dict(r) for r in conn.execute(sql,params).fetchall()];conn.close()
        return {"status":"ok","rows":rows}
