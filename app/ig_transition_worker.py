import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ig_broker_transition_watcher import run_transition_reconciliation

DXB = ZoneInfo("Asia/Dubai")

def now_dxb():
    return datetime.now(DXB).isoformat()

def loop_seconds(payload):
    watcher = payload.get("watcher", {}) or {}
    session = ((watcher.get("session_state") or {}).get("session")) or ""
    pending = int(watcher.get("pending_closes", 0) or 0)
    transition = watcher.get("transition_state")

    if session == "weekend_closed":
        return 300 if pending > 0 else 600
    if session == "sunday_reopen_probe":
        return 45 if pending > 0 else 60
    if transition in ("edits_only_transition", "reopen_probe"):
        return 45
    if transition == "fully_tradeable":
        return 60
    return 120

def main():
    while True:
        try:
            payload = run_transition_reconciliation()
            print(json.dumps({
                "ts": now_dxb(),
                "worker": "ig_transition",
                "ok": payload.get("ok", False),
                "watcher": payload.get("watcher", {}),
                "reconciliation_changed": len(((payload.get("reconciliation") or {}).get("changed") or [])),
                "reconciliation_items": len(((payload.get("reconciliation") or {}).get("items") or [])),
            }))
            sleep_for = loop_seconds(payload)
        except Exception as e:
            print(json.dumps({
                "ts": now_dxb(),
                "worker": "ig_transition",
                "ok": False,
                "error": str(e),
            }))
            sleep_for = 120

        time.sleep(sleep_for)

if __name__ == "__main__":
    main()
