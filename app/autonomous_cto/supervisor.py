from __future__ import annotations

import json
import time
import traceback
from datetime import datetime, timezone

from app.autonomous_cto import (
    state_store,
    policy_engine,
    diagnostics_engine,
    patch_planner,
    patch_executor,
    test_runner,
    merge_controller,
    deploy_controller,
    rollback_controller,
    report_writer,
)
from app.autonomous_cto.telegram_control import send_cto_message
from app.autonomous_cto.scheduler import Scheduler


class CTOSupervisor:
    def __init__(self) -> None:
        state_store.ensure_tables()
        self.scheduler = Scheduler()
        self._setup_schedule()

    def _setup_schedule(self) -> None:
        interval = policy_engine.diagnostic_interval_minutes() * 60
        self.scheduler.add_task("diagnostic_cycle", self.run_diagnostic_cycle, interval)
        self.scheduler.add_task("daily_report", self._write_daily_report, 86400)

    def _is_killed(self) -> bool:
        return bool(state_store.get_kv("cto_killed", False))

    def _log(self, stage: str, data: dict) -> None:
        print(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "cto": stage, **data}, default=str), flush=True)

    def run_forever(self) -> None:
        self._log("start", {"msg": "CTO supervisor starting"})
        send_cto_message("🤖 Autonomous CTO Agent started.")
        while True:
            try:
                self.scheduler.run_pending()
            except Exception as e:
                self._log("loop_error", {"error": str(e), "trace": traceback.format_exc()[-1000:]})
            time.sleep(30)

    def run_diagnostic_cycle(self) -> dict:
        if self._is_killed():
            self._log("killed", {"msg": "CTO killed — skipping diagnostic cycle"})
            return {"ok": False, "reason": "killed"}

        self._log("diagnostic_start", {})
        diagnosis = diagnostics_engine.run_full_diagnosis()
        overall_score = diagnosis.get("overall_score", 100)
        issues = diagnostics_engine.identify_top_issues(diagnosis)

        self._log("diagnostic_complete", {
            "score": overall_score,
            "issue_count": len(issues),
            "top_issue": issues[0].get("issue") if issues else None,
        })
        state_store.log_event("diagnostic", "info", f"score={overall_score} issues={len(issues)}")

        if issues and overall_score < 80:
            high_issues = [i for i in issues if i.get("severity") in ("critical", "high", "warning")]
            for issue in high_issues[:2]:  # handle top 2 issues per cycle
                self.handle_issue(issue, diagnosis)

        return {"ok": True, "score": overall_score, "issues": issues}

    def handle_issue(self, issue: dict, diagnosis: dict) -> None:
        if self._is_killed():
            return

        # Check daily patch budget and cooldown
        patches_today = state_store.patches_today()
        max_patches = policy_engine.max_patches_per_day()
        if patches_today >= max_patches:
            self._log("patch_budget_exhausted", {"patches_today": patches_today, "max": max_patches})
            return

        last_patch_ts = state_store.get_kv("last_patch_ts")
        if last_patch_ts:
            try:
                last = datetime.fromisoformat(last_patch_ts)
                elapsed_min = (datetime.now(timezone.utc) - last).total_seconds() / 60
                cooldown = policy_engine.patch_cooldown_minutes()
                if elapsed_min < cooldown:
                    self._log("patch_cooldown", {"elapsed_min": round(elapsed_min), "cooldown": cooldown})
                    return
            except Exception:
                pass

        severity = issue.get("severity", "warning")
        if severity not in ("critical", "high", "warning"):
            return

        self._log("handling_issue", {"issue": issue.get("issue"), "severity": severity})

        task_id = state_store.add_task(
            title=f"Auto: {issue.get('issue', 'unknown')[:60]}",
            description=f"{issue.get('suggested_action', '')} | Severity: {severity}",
            priority=1 if severity == "critical" else 3,
            source="auto_diagnostic",
        )

        patch_result = patch_planner.plan_patch_for_issue(issue, diagnosis)
        if not patch_result.get("ok") or not patch_result.get("patches"):
            self._log("no_patch_planned", {"issue": issue.get("issue"), "error": patch_result.get("error")})
            state_store.update_task_status(task_id, "no_patch_available")
            return

        self.execute_improvement(task_id, patch_result["patches"], issue, diagnosis)

    def execute_improvement(self, task_id: int, patches: list[dict], issue: dict, diagnosis: dict) -> dict:
        branch = f"cto/auto-{int(time.time())}"
        self._log("patch_execute_start", {"branch": branch, "patch_count": len(patches)})

        exec_result = patch_executor.apply_patch_plan(patches, branch)
        if not exec_result.get("ok"):
            self._log("patch_apply_failed", {"error": exec_result.get("error")})
            state_store.update_task_status(task_id, "patch_failed", exec_result.get("error"))
            return {"ok": False, "error": exec_result.get("error")}

        # Run tests on the patched branch
        test_result = test_runner.run_tests()
        self._log("tests_complete", {"ok": test_result.get("ok"), "passed": test_result.get("passed"), "failed": test_result.get("failed")})

        if not test_result.get("ok"):
            # Tests failed — clean up branch, don't merge
            import subprocess, os
            subprocess.run(["git", "checkout", "main"], capture_output=True, cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            subprocess.run(["git", "push", "origin", "--delete", branch], capture_output=True, cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            state_store.update_task_status(task_id, "tests_failed", f"passed={test_result.get('passed')} failed={test_result.get('failed')}")
            send_cto_message(f"❌ Auto-patch tests failed for: {issue.get('issue')}\nBranch {branch} not merged.")
            return {"ok": False, "error": "tests_failed"}

        can_merge, merge_reason = policy_engine.can_auto_merge(test_passed=True)
        if not can_merge:
            state_store.update_task_status(task_id, "pending_manual_merge")
            send_cto_message(f"⏸️ Patch ready but auto-merge blocked: {merge_reason}\nBranch: {branch}")
            return {"ok": True, "merged": False, "branch": branch}

        pr_result = merge_controller.open_pr(
            branch=branch,
            title=f"cto: auto-fix — {issue.get('issue', 'improvement')[:50]}",
            body=f"**Auto-generated by CTO agent**\n\nIssue: {issue.get('issue')}\nAction: {issue.get('suggested_action')}\n\nTests: {test_result.get('passed')} passed, {test_result.get('failed')} failed",
        )
        if not pr_result.get("ok"):
            state_store.update_task_status(task_id, "pr_failed", pr_result.get("error"))
            return {"ok": False, "error": "pr_failed"}

        pr_number = pr_result.get("number")
        self._log("pr_opened", {"number": pr_number, "url": pr_result.get("url")})

        # Merge immediately since tests passed locally
        if pr_number:
            merge_result = merge_controller.merge_when_ready(pr_number, wait_for_ci_minutes=15)
            if not merge_result.get("ok"):
                self._log("merge_failed", {"error": merge_result.get("error")})
                state_store.update_task_status(task_id, "merge_failed")
                return {"ok": False, "error": "merge_failed"}

        can_deploy, deploy_reason = policy_engine.can_auto_deploy(test_passed=True, merge_ok=True)
        if not can_deploy:
            state_store.update_task_status(task_id, "pending_deploy", f"deploy blocked: {deploy_reason}")
            return {"ok": True, "deployed": False}

        pre_health = diagnostics_engine.run_full_diagnosis()
        rollback_controller.save_pre_deploy_sha(pre_health.get("runtime", {}).get("deployed_sha", ""))

        deploy_result = deploy_controller.deploy(f"cto: auto-fix {issue.get('issue', 'improvement')[:40]}")
        state_store.set_kv("last_deploy_sha", deploy_result.get("deployed_sha", ""))
        state_store.set_kv("last_patch_ts", datetime.now(timezone.utc).isoformat())
        state_store.log_decision("patch_applied", f"patched {issue.get('issue')}", str(patches[0].get("description")), "deployed" if deploy_result.get("ok") else "deploy_failed")

        if deploy_result.get("ok"):
            send_cto_message(f"✅ Auto-patch deployed: {issue.get('issue')}\nSHA: {deploy_result.get('deployed_sha')}")
            self._post_deploy_verify(pre_health, deploy_result.get("deployed_sha", ""))
        else:
            send_cto_message(f"❌ Deploy failed after merge: {deploy_result.get('output', '')[:200]}")

        state_store.update_task_status(task_id, "done" if deploy_result.get("ok") else "deploy_failed")
        return {"ok": deploy_result.get("ok"), "deployed_sha": deploy_result.get("deployed_sha")}

    def _post_deploy_verify(self, pre_health: dict, deployed_sha: str) -> None:
        time.sleep(60)  # give services time to restart
        post_health = diagnostics_engine.run_full_diagnosis()
        should_rb, rb_reason = policy_engine.should_rollback(
            {"score": pre_health.get("overall_score", 100)},
            {"score": post_health.get("overall_score", 100), "critical": post_health.get("runtime", {}).get("critical", [])},
        )
        if should_rb:
            pre_sha = rollback_controller.get_pre_deploy_sha()
            rollback_controller.auto_rollback(deployed_sha, rb_reason)
        else:
            self._log("post_deploy_health_ok", {"score": post_health.get("overall_score")})

    def _write_daily_report(self) -> None:
        try:
            diagnosis = diagnostics_engine.run_full_diagnosis()
            decisions = state_store.get_recent_decisions(limit=20)
            tasks = state_store.get_pending_tasks(limit=20)
            path = report_writer.write_daily_report(diagnosis, decisions, tasks)
            self._log("daily_report_written", {"path": path})
        except Exception as e:
            self._log("daily_report_error", {"error": str(e)})
