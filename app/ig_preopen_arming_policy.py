from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.ig_market_hours_map import build_market_hours_map

DXB = ZoneInfo("Asia/Dubai")

def _now():
    return datetime.now(DXB)

def build_preopen_arming_policy(now=None):
    now = now.astimezone(DXB) if now else _now()
    hours = build_market_hours_map(now)

    wd = now.weekday()
    t = now.time()

    arming_state = "disarmed"
    execution_allowed = False
    max_batch = 0
    cooldown_seconds = 0
    notes = []

    # Sunday
    if wd == 6:
        if time(20, 0) <= t < time(23, 35):
            arming_state = "plan_only"
            max_batch = 0
            cooldown_seconds = 900
            notes.append("Sunday prep window: planning only.")
        elif time(23, 35) <= t < time(23, 50):
            arming_state = "armed_light"
            execution_allowed = True
            max_batch = 1
            cooldown_seconds = 900
            notes.append("Sunday preopen light reduction window.")
        elif t >= time(23, 50):
            arming_state = "armed_active"
            execution_allowed = True
            max_batch = 2
            cooldown_seconds = 600
            notes.append("Sunday transition window active.")

    # Monday
    if wd == 0:
        if time(0, 0) <= t < time(1, 0):
            arming_state = "armed_active"
            execution_allowed = True
            max_batch = 2
            cooldown_seconds = 600
            notes.append("Monday forex early-open supervision window.")
        elif time(1, 0) <= t < time(2, 0):
            arming_state = "armed_light"
            execution_allowed = True
            max_batch = 1
            cooldown_seconds = 900
            notes.append("Monday monitoring and light action window.")
        elif time(2, 0) <= t < time(3, 0):
            arming_state = "armed_index_transition"
            execution_allowed = True
            max_batch = 1
            cooldown_seconds = 900
            notes.append("Monday index transition validation window.")

    return {
        "timestamp": now.isoformat(),
        "market_hours": hours,
        "arming_state": arming_state,
        "execution_allowed": execution_allowed,
        "max_batch": max_batch,
        "cooldown_seconds": cooldown_seconds,
        "notes": notes,
    }
