import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ig_live_observation_engine import log_live_observation

DXB = ZoneInfo("Asia/Dubai")
LOOP_SECONDS = 60

def now_dxb():
    return datetime.now(DXB).isoformat()

def main():
    while True:
        try:
            result = log_live_observation()
            print(json.dumps({
                "ts": now_dxb(),
                "worker": "ig_decision_audit",
                "ok": True,
                "deploy_verdict": ((result.get("logged") or {}).get("deploy_verdict")),
                "master_score": ((result.get("logged") or {}).get("master_score")),
                "threshold_state": ((result.get("logged") or {}).get("threshold_state")),
                "summary_recent_count": ((result.get("summary") or {}).get("recent_count")),
            }))
        except Exception as e:
            print(json.dumps({
                "ts": now_dxb(),
                "worker": "ig_decision_audit",
                "ok": False,
                "error": str(e),
            }))
        time.sleep(LOOP_SECONDS)

if __name__ == "__main__":
    main()
