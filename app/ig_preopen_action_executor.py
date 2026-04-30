from app.ig_preopen_action_planner import build_preopen_action_plan
from app.ig_preopen_action_registry import add_preopen_action
from app.ig_forced_flatten_executor import run_forced_flatten
from app.ig_preopen_action_cooldown import get_preopen_cooldown, set_preopen_cooldown
from app.ig_preopen_window_policy import build_preopen_window_policy
from app.ig_api_governor import get_ig_cached_snapshot

def execute_preopen_action(max_batch=2, now=None, dry_run=False):
    plan = build_preopen_action_plan(now=now)
    action_type = plan.get("action_type")
    window = build_preopen_window_policy(now=now)
    cooldown = get_preopen_cooldown()

    effective_batch = min(int(max_batch), int(window.get("max_batch", 0) or 0)) if window.get("armed") else 0

    if action_type == "NO_ACTION":
        row = add_preopen_action({
            "action_type": action_type,
            "status": "SKIPPED",
            "reason": ["no_action_required"],
            "window_policy": window,
            "cooldown": cooldown,
            "dry_run": dry_run,
            "plan": plan,
        })
        return {"ok": True, "executed": False, "logged": row, "plan": plan, "window_policy": window, "cooldown": cooldown}

    if cooldown.get("active") and not dry_run:
        row = add_preopen_action({
            "action_type": action_type,
            "status": "BLOCKED",
            "reason": ["preopen_cooldown_active"],
            "window_policy": window,
            "cooldown": cooldown,
            "dry_run": dry_run,
            "plan": plan,
        })
        return {"ok": True, "executed": False, "logged": row, "plan": plan, "window_policy": window, "cooldown": cooldown}

    if not window.get("armed"):
        row = add_preopen_action({
            "action_type": action_type,
            "status": "BLOCKED",
            "reason": ["window_not_armed"],
            "window_policy": window,
            "cooldown": cooldown,
            "dry_run": dry_run,
            "plan": plan,
        })
        return {"ok": True, "executed": False, "logged": row, "plan": plan, "window_policy": window, "cooldown": cooldown}

    if action_type == "FORCE_FLATTEN_BATCH" and not window.get("force_flatten_allowed"):
        action_type = "REDUCE_RISK"

    if effective_batch <= 0:
        row = add_preopen_action({
            "action_type": action_type,
            "status": "BLOCKED",
            "reason": ["effective_batch_zero"],
            "window_policy": window,
            "cooldown": cooldown,
            "dry_run": dry_run,
            "plan": plan,
        })
        return {"ok": True, "executed": False, "logged": row, "plan": plan, "window_policy": window, "cooldown": cooldown}

    if dry_run:
        row = add_preopen_action({
            "action_type": action_type,
            "status": "SIMULATED",
            "reason": ["dry_run_only"],
            "window_policy": window,
            "cooldown": cooldown,
            "dry_run": True,
            "effective_batch": effective_batch,
            "plan": plan,
        })
        return {
            "ok": True,
            "executed": False,
            "logged": row,
            "plan": plan,
            "window_policy": window,
            "cooldown": cooldown,
        }

    if action_type in ("REDUCE_RISK", "FORCE_FLATTEN_BATCH"):
        result = run_forced_flatten(max_batch=effective_batch)
        status = "EXECUTED" if result.get("ok") else "FAILED"
        new_cd = set_preopen_cooldown(minutes=10, action_type=action_type, stage=window.get("stage"))
        row = add_preopen_action({
            "action_type": action_type,
            "status": status,
            "reason": result.get("reason", []),
            "submitted_count": len(result.get("submitted", []) or []),
            "window_policy": window,
            "cooldown": new_cd,
            "dry_run": False,
            "effective_batch": effective_batch,
            "plan": plan,
            "execution_result": result,
        })
        return {
            "ok": bool(result.get("ok")),
            "executed": True,
            "logged": row,
            "plan": plan,
            "window_policy": window,
            "cooldown": new_cd,
            "execution_result": result,
        }

    row = add_preopen_action({
        "action_type": action_type,
        "status": "BLOCKED",
        "reason": ["unsupported_action_type"],
        "window_policy": window,
        "cooldown": cooldown,
        "dry_run": dry_run,
        "plan": plan,
    })
    return {"ok": False, "executed": False, "logged": row, "plan": plan, "window_policy": window, "cooldown": cooldown}
