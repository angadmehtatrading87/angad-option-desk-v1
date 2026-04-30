from datetime import datetime, time
from zoneinfo import ZoneInfo

DXB = ZoneInfo("Asia/Dubai")

def _coerce_now(now=None):
    if now is None:
        return datetime.now(DXB)
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
    return datetime.now(DXB)

def build_market_hours_map(now=None):
    now = _coerce_now(now)
    wd = now.weekday()
    t = now.time()

    phase = "normal"
    if wd == 6 and time(23, 35) <= t < time(23, 50):
        phase = "sunday_preopen"
    elif wd == 6 and time(23, 50) <= t <= time(23, 59, 59):
        phase = "forex_transition_watch"
    elif wd == 0 and time(0, 0) <= t < time(1, 0):
        phase = "monday_forex_open_window"
    elif wd == 0 and time(1, 40) <= t < time(3, 0):
        phase = "monday_index_transition_window"

    return {
        "timestamp": now.isoformat(),
        "timezone": "Asia/Dubai",
        "weekday": wd,
        "phase": phase,
        "windows": {
            "forex_weekday_open_time_dxb": "00:00 Monday",
            "forex_preopen_check_time_dxb": "23:35 Sunday",
            "forex_transition_watch_start_dxb": "23:50 Sunday",
            "forex_post_open_checkpoints_dxb": [
                "00:15 Monday",
                "00:30 Monday",
                "01:00 Monday"
            ],
            "index_transition_check_time_dxb": "01:40 Monday",
            "index_transition_validation_time_dxb": "02:00 Monday",
            "archive_time_dxb": "03:00 Monday"
        },
        "notes": [
            "Forex supervision centers on late Sunday night into Monday 00:00 Dubai.",
            "Weekend/24h index supervision includes Monday 02:00 Dubai transition checkpoint.",
            "Keep DST sensitivity in mind; schedule logic should remain data-driven."
        ]
    }

def should_run_deep_preopen(now=None):
    phase = build_market_hours_map(now=now).get("phase")
    return phase in ("sunday_preopen", "monday_forex_open_window")

def should_run_transition_watch(now=None):
    phase = build_market_hours_map(now=now).get("phase")
    return phase in ("forex_transition_watch", "monday_index_transition_window")
