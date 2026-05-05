"""
Daily code-proposer worker.

Long-running. Wakes up every minute, checks the schedule in
config/agent_proposer.yaml, fires `run_one_proposal_cycle()` once per day.
Idempotent (state file in `data/agent_proposer_state.json`) so a restart
doesn't duplicate.

Run as systemd: `deploy/systemd/angad-code-proposer.service`.
"""

from __future__ import annotations

import json
import os
import time
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

import yaml

from app.agent_ops.code_proposer import run_one_proposal_cycle

DXB = ZoneInfo("Asia/Dubai")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_PATH = os.path.join(BASE_DIR, "data", "agent_proposer_state.json")
CONFIG_PATH = os.path.join(BASE_DIR, "config", "agent_proposer.yaml")


def _now() -> datetime:
    return datetime.now(DXB)


def _today_key() -> str:
    return _now().strftime("%Y-%m-%d")


def _load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_PATH)


def _load_schedule() -> tuple[list[int], list[int]]:
    if not os.path.exists(CONFIG_PATH):
        return ([2], [0])  # safe default: 02:00 Dubai
    try:
        with open(CONFIG_PATH, "r") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        return ([2], [0])
    hours = cfg.get("fire_at_dubai_hours", [2]) or [2]
    minutes = cfg.get("fire_at_dubai_minutes", [0]) or [0]
    return ([int(h) for h in hours], [int(m) for m in minutes])


def _due(state: dict, hours: list[int], minutes: list[int], now: datetime) -> bool:
    today = _today_key()
    if state.get("last_fired_date") == today:
        return False
    if now.hour in hours and now.minute in minutes:
        return True
    # If we missed the window (worker started up after the slot), allow up
    # to 30 min slack so a 02:00 fire doesn't get skipped because the
    # worker booted at 02:05.
    for h in hours:
        for m in minutes:
            slot_minutes = h * 60 + m
            now_minutes = now.hour * 60 + now.minute
            delta = now_minutes - slot_minutes
            if 0 <= delta <= 30:
                return True
    return False


def main():
    while True:
        try:
            state = _load_state()
            hours, minutes = _load_schedule()
            now = _now()
            if _due(state, hours, minutes, now):
                print(json.dumps({
                    "ts": now.isoformat(),
                    "worker": "code_proposer",
                    "stage": "fire",
                }))
                result = run_one_proposal_cycle()
                state["last_fired_date"] = _today_key()
                state["last_fired_at"] = now.isoformat()
                state["last_result"] = {
                    "ok": result.get("ok"),
                    "stage": result.get("stage"),
                    "rejected_reason": result.get("rejected_reason"),
                    "title": result.get("title"),
                    "usd_cost": result.get("usd_cost"),
                }
                _save_state(state)
                print(json.dumps({
                    "ts": _now().isoformat(),
                    "worker": "code_proposer",
                    "stage": "done",
                    "result": state["last_result"],
                }, default=str))
            time.sleep(60)
        except Exception:
            print(json.dumps({
                "ts": _now().isoformat(),
                "worker": "code_proposer",
                "ok": False,
                "stage": "exception",
                "traceback": traceback.format_exc()[:2000],
            }))
            time.sleep(60)


if __name__ == "__main__":
    main()
