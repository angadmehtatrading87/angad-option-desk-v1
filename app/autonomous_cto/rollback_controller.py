from __future__ import annotations

import subprocess
import os

from app.autonomous_cto import deploy_controller, state_store

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _git(*args: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(["git"] + list(args), capture_output=True, text=True, timeout=30, cwd=BASE_DIR)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


def rollback_to_commit(sha: str) -> dict:
    ok, out = _git("revert", sha, "--no-edit")
    if not ok:
        return {"ok": False, "error": f"git revert failed: {out}"}
    deploy_result = deploy_controller.deploy(f"cto: rollback revert of {sha}")
    return {
        "ok": deploy_result.get("ok"),
        "reverted_sha": sha,
        "deploy_result": deploy_result,
    }


def auto_rollback(bad_sha: str, reason: str) -> dict:
    from app.autonomous_cto.telegram_control import send_cto_message
    msg = f"⚠️ AUTO ROLLBACK TRIGGERED\nBad deploy: {bad_sha}\nReason: {reason}\nReverting..."
    send_cto_message(msg)

    result = rollback_to_commit(bad_sha)
    state_store.log_decision(
        decision_type="rollback",
        summary=f"auto-rollback of {bad_sha}",
        rationale=reason,
        outcome="ok" if result.get("ok") else "failed",
    )
    state_store.log_event("rollback", "critical", f"auto-rollback of {bad_sha}: {reason}")

    outcome_msg = "✅ Rollback deployed successfully." if result.get("ok") else f"❌ Rollback deploy FAILED: {result.get('error')}"
    send_cto_message(outcome_msg)
    return result


def get_pre_deploy_sha() -> str:
    return str(state_store.get_kv("pre_deploy_sha") or "")


def save_pre_deploy_sha(sha: str) -> None:
    state_store.set_kv("pre_deploy_sha", sha)
