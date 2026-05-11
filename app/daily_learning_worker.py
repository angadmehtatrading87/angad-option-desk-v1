"""
Daily learning worker — runs as a long-lived daemon.

At 01:30 Dubai time each day it reads the last 30 days of trades from
ig_trade_log, computes per-epic win rate and avg PnL pips, and writes
data/pair_edge_memory.json so agent_v2_orchestrator can load it as a
supplemental pair-edge signal.
"""

import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DXB = ZoneInfo("Asia/Dubai")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "pair_edge_memory.json")

RUN_HOUR = 1
RUN_MINUTE = 30


def _now_dxb() -> datetime:
    return datetime.now(DXB)


def _seconds_until_next_run() -> float:
    now = _now_dxb()
    target = now.replace(hour=RUN_HOUR, minute=RUN_MINUTE, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _load_trades_30d() -> list[dict]:
    if not os.path.exists(DB_PATH):
        return []
    cutoff = (_now_dxb() - timedelta(days=30)).isoformat()
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM ig_trade_log WHERE updated_at >= ? ORDER BY id DESC LIMIT 2000",
            (cutoff,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


def _is_win(row: dict) -> bool | None:
    """Return True=win, False=loss, None=unknown/open."""
    status = str(row.get("status") or "").upper()
    reason = str(row.get("reason") or "").lower()
    raw = str(row.get("raw_response") or "").lower()

    if status in ("CONFIRMED_IN_BOOK", "ACCEPTED_NOT_VISIBLE_IN_BOOK"):
        # Still open — skip for realized stats
        return None
    if status in ("SUBMITTING", "PENDING_CONFIRMATION"):
        return None

    # Closed trades: infer from reason text
    profit_keywords = ("profit", "harvest", "partial", "runner", "lock")
    loss_keywords = ("loss", "not working", "cut", "laggard", "weak signal", "stop")

    combined = reason + " " + raw
    if any(k in combined for k in profit_keywords):
        return True
    if any(k in combined for k in loss_keywords):
        return False
    # CLOSE_SUBMITTED without clear reason — treat as loss (conservative)
    if "close" in status:
        return False
    return None


def _safe_float(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def compute_pair_edge(rows: list[dict]) -> dict:
    by_epic: dict[str, dict] = {}

    for row in rows:
        epic = str(row.get("epic") or "").strip()
        if not epic:
            continue

        outcome = _is_win(row)
        if outcome is None:
            continue  # open / unknown — skip

        bucket = by_epic.setdefault(epic, {
            "trades": 0,
            "wins": 0,
            "pnl_pips_sum": 0.0,
            "last_outcome": None,
            "last_updated_at": "",
        })
        bucket["trades"] += 1
        if outcome:
            bucket["wins"] += 1
            bucket["pnl_pips_sum"] += _safe_float(row.get("limit_distance"), 0.0)
        else:
            bucket["pnl_pips_sum"] -= _safe_float(row.get("stop_distance"), 0.0)

        updated_at = str(row.get("updated_at") or "")
        if updated_at > bucket["last_updated_at"]:
            bucket["last_updated_at"] = updated_at
            bucket["last_outcome"] = "win" if outcome else "loss"

    result: dict[str, dict] = {}
    for epic, b in by_epic.items():
        n = max(b["trades"], 1)
        wins = b["wins"]
        result[epic] = {
            "trades_30d": b["trades"],
            "wins_30d": wins,
            "win_rate": round((wins / n) * 100.0, 2),
            "avg_pnl_pips": round(b["pnl_pips_sum"] / n, 2),
            "last_outcome": b["last_outcome"],
        }
    return result


def run_learning_cycle() -> None:
    rows = _load_trades_30d()
    by_epic = compute_pair_edge(rows)
    payload = {
        "updated_at": _now_dxb().isoformat(),
        "by_epic": by_epic,
    }
    tmp = OUTPUT_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, OUTPUT_PATH)
    print(json.dumps({
        "ts": payload["updated_at"],
        "worker": "daily_learning",
        "stage": "cycle_complete",
        "epics": len(by_epic),
        "total_rows": len(rows),
    }), flush=True)


def main() -> None:
    print(json.dumps({
        "ts": _now_dxb().isoformat(),
        "worker": "daily_learning",
        "stage": "start",
        "next_run_hour": RUN_HOUR,
        "next_run_minute": RUN_MINUTE,
    }), flush=True)

    while True:
        wait = _seconds_until_next_run()
        print(json.dumps({
            "ts": _now_dxb().isoformat(),
            "worker": "daily_learning",
            "stage": "sleeping",
            "seconds_until_run": round(wait),
        }), flush=True)
        time.sleep(wait)

        try:
            run_learning_cycle()
        except Exception as exc:
            print(json.dumps({
                "ts": _now_dxb().isoformat(),
                "worker": "daily_learning",
                "stage": "error",
                "error": str(exc),
            }), flush=True)

        # Sleep 90s after the run to avoid re-triggering in the same minute
        time.sleep(90)


if __name__ == "__main__":
    main()
