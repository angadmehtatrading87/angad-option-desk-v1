import json
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ig_preopen_action_executor import execute_preopen_action

DXB = ZoneInfo("Asia/Dubai")


def main():
    now = datetime.now(DXB).isoformat()
    result = execute_preopen_action(now=now, dry_run=False)

    logged = (result or {}).get("logged", {}) or {}
    window_policy = logged.get("window_policy", {}) or {}
    cooldown = logged.get("cooldown", {}) or {}
    plan = logged.get("plan", {}) or {}

    compact = {
        "ts": now,
        "worker": "ig_preopen_action",
        "ok": bool((result or {}).get("ok")),
        "executed": bool((result or {}).get("executed")),
        "status": logged.get("status"),
        "action_type": logged.get("action_type"),
        "stage": window_policy.get("stage"),
        "armed": window_policy.get("armed"),
        "max_batch": window_policy.get("max_batch"),
        "cooldown_active": cooldown.get("active"),
        "reason": logged.get("reason", []),
        "effective_batch": logged.get("effective_batch"),
        "candidate_count": plan.get("candidate_count"),
    }

    print(json.dumps(compact))


if __name__ == "__main__":
    main()
