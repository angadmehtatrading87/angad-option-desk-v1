import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ig_adapter import IGAdapter
from app.ig_execution_engine import eligible_decisions, run_ig_demo_execution
from app.market_brain_execution_bridge import build_market_brain_execution_pick, market_brain_execution_config
from app.execution_safety_guard import evaluate_execution_safety
from app.telegram_control_room.status_provider import update_runtime

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
                update_runtime({
                    "worker_status": "alive",
                    "last_worker_loop_time": now_dxb(),
                    "ig_execution_worker_last_run_status": "login_failed",
                    "ig_execution_worker_last_decision_count": 0,
                    "ig_execution_worker_last_rejection_reason": "ig_login_failed",
                    "ig_execution_worker_status": "inactive",
                })
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
                update_runtime({
                    "worker_status": "alive",
                    "last_worker_loop_time": now_dxb(),
                    "ig_execution_worker_last_run_status": "safety_blocked",
                    "ig_execution_worker_last_decision_count": 0,
                    "ig_execution_worker_last_rejection_reason": ",".join([str(x) for x in safety.get("reasons", [])])[:500],
                    "ig_execution_worker_status": "inactive",
                })
                print(json.dumps({"ts": now_dxb(), "worker": "ig_execution", "stage": "safety", "ok": False, "reason": safety.get("reasons", [])}, default=str))
                time.sleep(LOOP_SECONDS)
                continue

            mb_cfg = market_brain_execution_config()
            pick = build_market_brain_execution_pick(ig=ig) if mb_cfg.get("enabled") else eligible_decisions(ig=ig, login=login)
            pick_reason = pick.get("reason", [])
            bridge = pick.get("bridge", {}) if isinstance(pick, dict) else {}
            cap_util = bridge.get("capital_utilization", {}) if isinstance(bridge, dict) else {}
            update_runtime({
                "worker_status": "alive",
                "last_worker_loop_time": now_dxb(),
                "ig_execution_worker_last_decision_count": len(pick.get("decisions", [])),
                "ig_execution_worker_last_rejection_reason": ",".join([str(x) for x in pick_reason])[:500] if pick_reason else None,
                "ig_execution_worker_status": "running" if pick.get("ok") else "inactive",
                "market_brain_execution_enabled": bool(mb_cfg.get("enabled")),
                "market_brain_execution_mode": mb_cfg.get("mode"),
                "market_brain_last_trade_candidate": (pick.get("decisions") or [None])[0],
                "market_brain_last_rejection_reason": (pick.get("skips") or [{}])[0].get("reason") if pick.get("skips") else None,
                "capital_utilization": cap_util,
            })

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
            executed = None
            for row in result.get("submitted", []):
                if str(row.get("status", "")).upper() in ("SIMULATED", "CONFIRMED_IN_BOOK", "ACCEPTED_NOT_VISIBLE_IN_BOOK"):
                    executed = row
                    break
            update_runtime({
                "worker_status": "alive",
                "last_worker_loop_time": now_dxb(),
                "ig_execution_worker_last_run_status": "ok" if result.get("ok") else "error",
                "last_error": None if result.get("ok") else str(result.get("reason", []))[:500],
                "market_brain_last_executed_trade": executed,
            })

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
            update_runtime({
                "worker_status": "alive",
                "last_worker_loop_time": now_dxb(),
                "ig_execution_worker_last_run_status": "exception",
                "last_error": str(e)[:500],
                "ig_execution_worker_status": "inactive",
            })
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
