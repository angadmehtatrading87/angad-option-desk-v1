import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ig_adapter import IGAdapter
from app.ig_execution_engine import eligible_decisions, run_ig_demo_execution
from app.execution_safety_guard import evaluate_execution_safety

DXB = ZoneInfo("Asia/Dubai")
LOOP_SECONDS = 30

def now_dxb():
    return datetime.now(DXB).isoformat()

def main():
    while True:
        try:
            ig = IGAdapter()
            login = ig.login()

            if not login.get("ok"):
                print(json.dumps({
                    "ts": now_dxb(),
                    "worker": "ig_execution",
                    "ok": False,
                    "stage": "login",
                    "reason": "ig_login_failed"
                }))
                time.sleep(LOOP_SECONDS)
                continue

            safety = evaluate_execution_safety(channel="ig_execution_worker", expected_order_count=1)
            if not safety.get("ok"):
                print(json.dumps({"ts": now_dxb(), "worker": "ig_execution", "stage": "safety", "ok": False, "reason": safety.get("reasons", [])}, default=str))
                time.sleep(LOOP_SECONDS)
                continue

            pick = eligible_decisions(ig=ig, login=login)
            pick_reason = pick.get("reason", [])

            print(json.dumps({
                "ts": now_dxb(),
                "worker": "ig_execution",
                "stage": "eligible",
                "ok": pick.get("ok"),
                "reason": pick_reason,
                "decision_count": len(pick.get("decisions", [])),
                "skip_count": len(pick.get("skips", [])),
                "decisions": pick.get("decisions", []),
                "skips": pick.get("skips", []),
            }, default=str))

            if (not pick.get("ok")) and ("combined_daily_target_hit_soft_lock" in pick_reason):
                precomputed = {"ok": True, "decisions": [], "skips": pick.get("skips", [])}
            else:
                precomputed = pick

            result = run_ig_demo_execution(precomputed_pick=precomputed, ig=ig, login=login)

            print(json.dumps({
                "ts": now_dxb(),
                "worker": "ig_execution",
                "stage": "run",
                "ok": result.get("ok"),
                "reason": result.get("reason", []),
                "submitted": result.get("submitted", []),
                "closed": result.get("closed", []),
                "skips": result.get("skips", []),
            }, default=str))

            time.sleep(LOOP_SECONDS)

        except Exception as e:
            print(json.dumps({
                "ts": now_dxb(),
                "worker": "ig_execution",
                "ok": False,
                "stage": "exception",
                "error": str(e)
            }))
            time.sleep(LOOP_SECONDS)

if __name__ == "__main__":
    main()
