from app.ig_preopen_window_policy import build_preopen_window_policy
from app.ig_preopen_action_executor import execute_preopen_action

TEST_TIMES = [
    "2026-04-26T20:30:00+04:00",
    "2026-04-26T23:36:00+04:00",
    "2026-04-26T23:52:00+04:00",
    "2026-04-27T00:15:00+04:00",
    "2026-04-27T01:15:00+04:00",
    "2026-04-27T02:10:00+04:00",
]

def run_preopen_transition_simulation():
    rows = []
    for ts in TEST_TIMES:
        policy = build_preopen_window_policy(now=ts)
        result = execute_preopen_action(max_batch=3, now=ts, dry_run=True)
        rows.append({
            "test_time": ts,
            "stage": policy.get("stage"),
            "armed": policy.get("armed"),
            "max_batch": policy.get("max_batch"),
            "force_flatten_allowed": policy.get("force_flatten_allowed"),
            "action_type": ((result.get("plan") or {}).get("action_type")),
            "result_status": ((result.get("logged") or {}).get("status")),
            "reason": ((result.get("logged") or {}).get("reason")),
            "effective_batch": ((result.get("logged") or {}).get("effective_batch")),
        })
    return {
        "ok": True,
        "count": len(rows),
        "rows": rows,
    }
