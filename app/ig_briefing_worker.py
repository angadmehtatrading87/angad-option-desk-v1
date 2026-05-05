"""
IG-FX briefing worker.

Sends Telegram briefings at three Dubai-time anchors per day:
    06:30  — pre-London open
    14:30  — pre-NY open
    23:30  — post-NY close (day recap)

Idempotent: the worker writes a small JSON state file
(`data/ig_briefing_state.json`) recording the last-sent UTC timestamp per
slot, so a restart inside the same minute won't double-send.

This replaces the legacy `owner_reporting_worker.py` which sent
equities-options briefings.

Run as systemd: `deploy/systemd/angad-ig-briefing.service`.
"""

from __future__ import annotations

import json
import os
import time
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ig_briefing import build_pre_session_briefing, build_post_session_recap

DXB = ZoneInfo("Asia/Dubai")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(BASE_DIR, "data", "ig_briefing_state.json")

# (label, hour, minute, kind)
# kind ∈ {"pre", "recap"}.
SCHEDULE = [
    ("pre_london", 6, 30, "pre"),
    ("pre_ny",     14, 30, "pre"),
    ("post_ny",    23, 30, "recap"),
]

# How early/late we tolerate firing. If the worker starts up after the slot
# already passed today, we only fire if we're still within this window.
SLOT_TOLERANCE_MINUTES = 15


def _now_dxb() -> datetime:
    return datetime.now(DXB)


def _today_key() -> str:
    return _now_dxb().strftime("%Y-%m-%d")


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


def _previous_day_equity() -> float | None:
    """Best-effort yesterday's closing equity, for day-over-day delta in
    the recap. Reads from `data/daily_objective_state.json` if present."""
    path = os.path.join(BASE_DIR, "data", "daily_objective_state.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            state = json.load(f)
    except Exception:
        return None

    # state is keyed by date. Find yesterday's entry.
    today = _today_key()
    dates = sorted([k for k in state.keys() if k != today])
    if not dates:
        return None
    yest = state.get(dates[-1]) or {}
    start = yest.get("start") or {}
    return start.get("ig_equity") or start.get("combined_equity")


def _send_telegram_safe(message: str) -> dict:
    try:
        from app.telegram_alerts import send_telegram_message
        send_telegram_message(message)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _due(slot_label: str, slot_hour: int, slot_minute: int, state: dict, now: datetime) -> bool:
    """Has this slot already fired today?"""
    today = _today_key()
    last_sent = (state.get(slot_label) or {}).get("date")
    if last_sent == today:
        return False

    # Are we inside the firing window for this slot?
    slot_minutes = slot_hour * 60 + slot_minute
    now_minutes = now.hour * 60 + now.minute
    delta = now_minutes - slot_minutes
    if 0 <= delta <= SLOT_TOLERANCE_MINUTES:
        return True
    return False


def _fire_slot(slot_label: str, kind: str, state: dict) -> None:
    if kind == "pre":
        msg = build_pre_session_briefing()
    elif kind == "recap":
        msg = build_post_session_recap(prev_equity=_previous_day_equity())
    else:
        return

    result = _send_telegram_safe(msg)
    state[slot_label] = {
        "date": _today_key(),
        "sent_at": _now_dxb().isoformat(),
        "ok": result.get("ok"),
        "error": result.get("error"),
    }
    _save_state(state)
    print(json.dumps({
        "ts": _now_dxb().isoformat(),
        "worker": "ig_briefing",
        "slot": slot_label,
        "kind": kind,
        "ok": result.get("ok"),
        "error": result.get("error"),
    }, default=str))


def main():
    while True:
        try:
            now = _now_dxb()
            state = _load_state()
            for label, hour, minute, kind in SCHEDULE:
                if _due(label, hour, minute, state, now):
                    _fire_slot(label, kind, state)
            # Tick every 60 seconds. Slot resolution is 1 minute.
            time.sleep(60)
        except Exception:
            print(json.dumps({
                "ts": _now_dxb().isoformat(),
                "worker": "ig_briefing",
                "ok": False,
                "stage": "exception",
                "traceback": traceback.format_exc()[:2000],
            }))
            time.sleep(60)


if __name__ == "__main__":
    main()
