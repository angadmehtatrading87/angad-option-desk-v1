from __future__ import annotations

import time
from app.autonomous_cto.github_monitor import list_recent_workflow_runs, _gh


def get_ci_status() -> dict:
    runs = list_recent_workflow_runs(limit=5)
    if not runs:
        return {"ok": False, "status": "unknown", "conclusion": None}
    latest = runs[0]
    return {
        "ok": True,
        "run_id": latest.get("databaseId"),
        "name": latest.get("name"),
        "status": latest.get("status"),
        "conclusion": latest.get("conclusion"),
        "branch": latest.get("headBranch"),
        "created_at": latest.get("createdAt"),
    }


def is_ci_passing() -> bool:
    ci = get_ci_status()
    return ci.get("status") == "completed" and ci.get("conclusion") == "success"


def get_failed_workflow_logs(run_id: str) -> str:
    ok, out = _gh("run", "view", str(run_id), "--log-failed")
    return out if ok else f"[could not fetch logs for run {run_id}: {out}]"


def wait_for_ci(branch: str | None = None, timeout_minutes: int = 15) -> bool:
    deadline = time.time() + timeout_minutes * 60
    while time.time() < deadline:
        runs = list_recent_workflow_runs(limit=10)
        relevant = [r for r in runs if branch is None or r.get("headBranch") == branch]
        if not relevant:
            time.sleep(20)
            continue
        latest = relevant[0]
        status = latest.get("status")
        conclusion = latest.get("conclusion")
        if status == "completed":
            return conclusion == "success"
        time.sleep(20)
    return False
