from datetime import datetime, time
from zoneinfo import ZoneInfo

DXB = ZoneInfo("Asia/Dubai")

def _now():
    return datetime.now(DXB)

def _coerce_now(now=None):
    if now is None:
        return _now()
    if isinstance(now, str):
        dt = datetime.fromisoformat(now)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=DXB)
        else:
            dt = dt.astimezone(DXB)
        return dt
    if isinstance(now, datetime):
        if now.tzinfo is None:
            return now.replace(tzinfo=DXB)
        return now.astimezone(DXB)
    return _now()

def build_preopen_window_policy(now=None):
    now = _coerce_now(now)
    wd = now.weekday()
    t = now.time()

    stage = "inactive"
    armed = False
    max_batch = 0
    reduce_only = True
    force_flatten_allowed = False
    notes = []

    if wd == 6 and time(20, 0) <= t < time(23, 35):
        stage = "sunday_precheck"
        armed = False
        max_batch = 0
        notes.append("Planning only. No execution yet.")
    elif wd == 6 and time(23, 35) <= t < time(23, 50):
        stage = "sunday_arm_reduce"
        armed = True
        max_batch = 1
        notes.append("Allow only light risk reduction before transition watch.")
    elif wd == 6 and time(23, 50) <= t <= time(23, 59, 59):
        stage = "sunday_transition_watch"
        armed = True
        max_batch = 2
        notes.append("Transition watch live. Controlled reduction allowed.")
    elif wd == 0 and time(0, 0) <= t < time(1, 0):
        stage = "monday_forex_first_hour"
        armed = True
        max_batch = 2
        notes.append("Post-open first hour. Controlled reduction allowed.")
    elif wd == 0 and time(1, 0) <= t < time(2, 0):
        stage = "monday_forex_stabilization"
        armed = True
        max_batch = 3
        notes.append("Stabilization hour. Broader cleanup allowed.")
    elif wd == 0 and time(2, 0) <= t < time(3, 0):
        stage = "monday_index_transition"
        armed = True
        max_batch = 3
        force_flatten_allowed = True
        notes.append("Index transition window. Full cleanup allowed if needed.")

    return {
        "timestamp": now.isoformat(),
        "weekday": wd,
        "stage": stage,
        "armed": armed,
        "max_batch": max_batch,
        "reduce_only": reduce_only,
        "force_flatten_allowed": force_flatten_allowed,
        "notes": notes,
    }
