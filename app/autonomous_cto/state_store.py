from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "cto_agent.db")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables() -> None:
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS cto_kv (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cto_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                priority INTEGER DEFAULT 5,
                status TEXT DEFAULT 'pending',
                source TEXT,
                llm_plan TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cto_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_type TEXT NOT NULL,
                summary TEXT,
                rationale TEXT,
                outcome TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cto_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                severity TEXT DEFAULT 'info',
                details TEXT,
                created_at TEXT NOT NULL
            );
        """)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_kv(key: str, default: Any = None) -> Any:
    try:
        with _conn() as conn:
            row = conn.execute("SELECT value FROM cto_kv WHERE key = ?", (key,)).fetchone()
            if row is None:
                return default
            try:
                return json.loads(row["value"])
            except Exception:
                return row["value"]
    except Exception:
        return default


def set_kv(key: str, value: Any) -> None:
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cto_kv(key, value, updated_at) VALUES(?,?,?)",
                (key, json.dumps(value), _now()),
            )
    except Exception:
        pass


def add_task(title: str, description: str, priority: int = 5, source: str = "system") -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO cto_tasks(title, description, priority, source, created_at, updated_at) VALUES(?,?,?,?,?,?)",
            (title, description, priority, source, _now(), _now()),
        )
        return cur.lastrowid or 0


def get_pending_tasks(limit: int = 10) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM cto_tasks WHERE status='pending' ORDER BY priority ASC, id ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_tasks(limit: int = 50) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM cto_tasks ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def update_task_status(task_id: int, status: str, outcome: str | None = None, llm_plan: str | None = None) -> None:
    with _conn() as conn:
        if llm_plan is not None:
            conn.execute(
                "UPDATE cto_tasks SET status=?, llm_plan=?, updated_at=? WHERE id=?",
                (status, llm_plan, _now(), task_id),
            )
        else:
            conn.execute(
                "UPDATE cto_tasks SET status=?, updated_at=? WHERE id=?",
                (status, _now(), task_id),
            )


def log_decision(decision_type: str, summary: str, rationale: str, outcome: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO cto_decisions(decision_type, summary, rationale, outcome, created_at) VALUES(?,?,?,?,?)",
            (decision_type, summary, rationale, outcome, _now()),
        )


def log_event(event_type: str, severity: str = "info", details: str = "") -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO cto_events(event_type, severity, details, created_at) VALUES(?,?,?,?)",
            (event_type, severity, details, _now()),
        )


def get_recent_events(hours: int = 24) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM cto_events WHERE created_at >= datetime('now', ? || ' hours') ORDER BY id DESC",
            (f"-{hours}",),
        ).fetchall()
        return [dict(r) for r in rows]


def get_recent_decisions(limit: int = 20) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM cto_decisions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def patches_today() -> int:
    with _conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as n FROM cto_decisions WHERE decision_type='patch_applied' AND created_at >= datetime('now', 'start of day')"
        ).fetchone()
        return int(row["n"]) if row else 0
