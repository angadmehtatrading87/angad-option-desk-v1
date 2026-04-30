from datetime import datetime, time
from zoneinfo import ZoneInfo

DXB = ZoneInfo("Asia/Dubai")

BLOCK_START = time(17, 30)
BLOCK_END = time(23, 59, 59)

def us_options_entries_allowed():
    now = datetime.now(DXB).time()
    if BLOCK_START <= now <= BLOCK_END:
        return False, "us_options_paused_1730_to_0000_dubai"
    return True, "ok"
