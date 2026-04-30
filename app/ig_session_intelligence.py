from datetime import datetime, time
from zoneinfo import ZoneInfo

DXB = ZoneInfo("Asia/Dubai")

def _now():
    return datetime.now(DXB)

def get_ig_session_state(now=None):
    if isinstance(now, str):
        now = datetime.fromisoformat(now)
    now = now or _now()
    wd = now.weekday()  # Mon=0 ... Sun=6
    hhmm = now.time()

    session = "off_hours"
    market_open = False
    liquidity = "low"
    entry_mode = "blocked"
    carry_bias = "flat"
    notes = []

    if wd in (0, 1, 2, 3):
        if time(0, 0) <= hhmm < time(10, 0):
            session = "asia"
            market_open = True
            liquidity = "medium"
            entry_mode = "normal"
            carry_bias = "selective"
            notes.append("Asia session active.")
        elif time(10, 0) <= hhmm < time(16, 30):
            session = "london"
            market_open = True
            liquidity = "high"
            entry_mode = "aggressive"
            carry_bias = "selective"
            notes.append("London session active.")
        elif time(16, 30) <= hhmm < time(21, 30):
            session = "new_york"
            market_open = True
            liquidity = "high"
            entry_mode = "aggressive"
            carry_bias = "selective"
            notes.append("New York session active.")
        elif time(21, 30) <= hhmm < time(23, 59):
            session = "late_us"
            market_open = True
            liquidity = "medium"
            entry_mode = "reduced"
            carry_bias = "light"
            notes.append("Late US session; reduce aggression.")
        else:
            session = "overnight_gap"
            market_open = False
            liquidity = "low"
            entry_mode = "blocked"
            carry_bias = "flat"
            notes.append("Overnight/off-session window.")

    elif wd == 4:
        if time(0, 0) <= hhmm < time(10, 0):
            session = "asia_friday"
            market_open = True
            liquidity = "medium"
            entry_mode = "normal"
            carry_bias = "light"
            notes.append("Friday Asia session.")
        elif time(10, 0) <= hhmm < time(16, 0):
            session = "london_friday"
            market_open = True
            liquidity = "high"
            entry_mode = "normal"
            carry_bias = "light"
            notes.append("Friday London session.")
        elif time(16, 0) <= hhmm < time(19, 0):
            session = "friday_reduction"
            market_open = True
            liquidity = "medium"
            entry_mode = "reduced"
            carry_bias = "reduce"
            notes.append("Friday reduction window; avoid fresh risk.")
        elif time(19, 0) <= hhmm <= time(23, 59):
            session = "friday_close_window"
            market_open = False
            liquidity = "low"
            entry_mode = "blocked"
            carry_bias = "flatten"
            notes.append("Friday close window; flatten non-essential positions.")
        else:
            session = "pre_asia_friday"
            market_open = False
            liquidity = "low"
            entry_mode = "blocked"
            carry_bias = "flat"

    elif wd == 5:
        session = "weekend_closed"
        market_open = False
        liquidity = "closed"
        entry_mode = "blocked"
        carry_bias = "flat"
        notes.append("Weekend closed.")

    elif wd == 6:
        if hhmm < time(23, 0):
            session = "weekend_closed"
            market_open = False
            liquidity = "closed"
            entry_mode = "blocked"
            carry_bias = "flat"
            notes.append("Weekend closed before FX reopen.")
        else:
            session = "sunday_reopen_probe"
            market_open = True
            liquidity = "thin"
            entry_mode = "probe_only"
            carry_bias = "very_light"
            notes.append("Sunday reopen: probe only, reduced size.")

    return {
        "timestamp": now.isoformat(),
        "weekday": wd,
        "session": session,
        "market_open": market_open,
        "liquidity": liquidity,
        "entry_mode": entry_mode,
        "carry_bias": carry_bias,
        "notes": notes,
    }
