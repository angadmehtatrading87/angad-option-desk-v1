import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ig_sunday_supervisor import run_sunday_supervisor

DXB = ZoneInfo("Asia/Dubai")
LOOP_SECONDS = 300

def now_dxb():
    return datetime.now(DXB).isoformat()

def main():
    while True:
        try:
            result = run_sunday_supervisor()
            checklist = result.get("checklist", {}) or {}
            summary = checklist.get("summary", {}) or {}
            consistency = result.get("consistency", {}) or {}
            print(json.dumps({
                "ts": now_dxb(),
                "worker": "ig_sunday_supervisor",
                "ok": result.get("ok", False),
                "phase": ((result.get("market_hours") or {}).get("phase")),
                "overall_status": checklist.get("overall_status"),
                "deploy_verdict": summary.get("deploy_verdict"),
                "master_score": summary.get("master_score"),
                "consistency_ok": consistency.get("ok", True),
                "issues": consistency.get("issues", []),
            }))
        except Exception as e:
            print(json.dumps({
                "ts": now_dxb(),
                "worker": "ig_sunday_supervisor",
                "ok": False,
                "error": str(e),
            }))
        time.sleep(LOOP_SECONDS)

if __name__ == "__main__":
    main()
