from __future__ import annotations

from app.autonomous_cto.github_monitor import create_pr, auto_merge_pr, get_pr_status, close_pr
from app.autonomous_cto.workflow_monitor import wait_for_ci


def open_pr(branch: str, title: str, body: str) -> dict:
    return create_pr(branch=branch, title=title, body=body)


def get_pr_checks(pr_number: int) -> dict:
    return get_pr_status(pr_number)


def merge_when_ready(pr_number: int, wait_for_ci_minutes: int = 15) -> dict:
    pr = get_pr_status(pr_number)
    if not pr.get("ok"):
        return {"ok": False, "error": "could not fetch PR status"}

    branch = pr.get("headRefName", "")
    ci_ok = wait_for_ci(branch=branch, timeout_minutes=wait_for_ci_minutes)
    if not ci_ok:
        return {"ok": False, "error": "CI did not pass within timeout", "pr_number": pr_number}

    result = auto_merge_pr(pr_number)
    return {**result, "pr_number": pr_number, "branch": branch}


def close_stale_pr(pr_number: int, reason: str) -> bool:
    return close_pr(pr_number, reason)
