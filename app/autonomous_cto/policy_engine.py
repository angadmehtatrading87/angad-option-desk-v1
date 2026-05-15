from __future__ import annotations

import json
import os
from typing import Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
POLICY_PATH = os.path.join(BASE_DIR, "config", "cto_policy.json")

_DEFAULTS: dict[str, Any] = {
    "auto_merge_on_test_pass": True,
    "auto_deploy_after_merge": True,
    "require_ci_pass_before_merge": True,
    "rollback_if_health_drops_by": 20,
    "max_patches_per_day": 10,
    "patch_cooldown_minutes": 30,
    "diagnostic_interval_minutes": 15,
    "min_health_score_to_patch": 30,
    "max_concurrent_open_prs": 3,
    "allowed_patch_files": ["app/", "config/"],
    "forbidden_patch_files": ["push-and-deploy.sh", ".github/workflows/", "deploy/systemd/"],
    "telegram_notify_on": ["deploy", "rollback", "patch_applied", "issue_detected", "daily_report"],
}


def load_policy() -> dict[str, Any]:
    try:
        with open(POLICY_PATH) as f:
            on_disk = json.load(f)
        return {**_DEFAULTS, **on_disk}
    except Exception:
        return dict(_DEFAULTS)


def can_auto_merge(test_passed: bool, risk_level: str = "low") -> tuple[bool, str]:
    p = load_policy()
    if not p.get("auto_merge_on_test_pass"):
        return False, "auto_merge disabled by policy"
    if not test_passed:
        return False, "tests did not pass"
    if risk_level == "high" and not p.get("auto_merge_high_risk", False):
        return False, "high-risk patch requires manual approval"
    return True, "ok"


def can_auto_deploy(test_passed: bool, merge_ok: bool) -> tuple[bool, str]:
    p = load_policy()
    if not p.get("auto_deploy_after_merge"):
        return False, "auto_deploy disabled by policy"
    if not merge_ok:
        return False, "merge did not succeed"
    if not test_passed:
        return False, "tests did not pass"
    return True, "ok"


def should_rollback(pre_health: dict, post_health: dict) -> tuple[bool, str]:
    p = load_policy()
    threshold = float(p.get("rollback_if_health_drops_by", 20))
    pre_score = float(pre_health.get("score", 100))
    post_score = float(post_health.get("score", 100))
    drop = pre_score - post_score
    if drop >= threshold:
        return True, f"health dropped {drop:.1f} points (threshold {threshold})"
    post_critical = post_health.get("critical", [])
    if post_critical:
        return True, f"critical services down after deploy: {post_critical}"
    return False, "health ok"


def max_patches_per_day() -> int:
    return int(load_policy().get("max_patches_per_day", 10))


def patch_cooldown_minutes() -> int:
    return int(load_policy().get("patch_cooldown_minutes", 30))


def diagnostic_interval_minutes() -> int:
    return int(load_policy().get("diagnostic_interval_minutes", 15))


def file_patch_allowed(filepath: str) -> tuple[bool, str]:
    p = load_policy()
    for forbidden in p.get("forbidden_patch_files", []):
        if forbidden in filepath:
            return False, f"file matches forbidden pattern: {forbidden}"
    for allowed in p.get("allowed_patch_files", []):
        if filepath.startswith(allowed):
            return True, "ok"
    return False, "file not in allowed patch paths"


def notify_on(event: str) -> bool:
    return event in load_policy().get("telegram_notify_on", [])
