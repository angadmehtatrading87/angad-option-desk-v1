from __future__ import annotations

import json
import subprocess


def _gh(*args: str, timeout: int = 30) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["gh"] + list(args),
            capture_output=True, text=True, timeout=timeout,
        )
        return r.returncode == 0, r.stdout.strip()
    except FileNotFoundError:
        return False, "gh CLI not found"
    except subprocess.TimeoutExpired:
        return False, "gh_timeout"
    except Exception as e:
        return False, str(e)


def list_open_prs() -> list[dict]:
    ok, out = _gh("pr", "list", "--json", "number,title,state,headRefName,statusCheckRollup,createdAt", "--limit", "20")
    if not ok:
        return []
    try:
        return json.loads(out)
    except Exception:
        return []


def get_pr_status(pr_number: int) -> dict:
    ok, out = _gh("pr", "view", str(pr_number), "--json",
                  "number,title,state,headRefName,statusCheckRollup,mergeable,baseRefName")
    if not ok:
        return {"ok": False, "error": out}
    try:
        data = json.loads(out)
        checks = data.get("statusCheckRollup") or []
        ci_passing = all(c.get("conclusion") in ("SUCCESS", "SKIPPED") for c in checks) if checks else None
        return {**data, "ok": True, "ci_passing": ci_passing, "check_count": len(checks)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_recent_workflow_runs(limit: int = 10) -> list[dict]:
    ok, out = _gh("run", "list", "--json", "databaseId,name,status,conclusion,createdAt,headBranch", "--limit", str(limit))
    if not ok:
        return []
    try:
        return json.loads(out)
    except Exception:
        return []


def get_latest_commit() -> dict:
    ok, out = _gh("api", "repos/{owner}/{repo}/commits/HEAD")
    if not ok:
        return {"ok": False}
    try:
        data = json.loads(out)
        return {
            "ok": True,
            "sha": data.get("sha", "")[:8],
            "message": (data.get("commit") or {}).get("message", "")[:80],
            "author": ((data.get("commit") or {}).get("author") or {}).get("name", ""),
            "date": ((data.get("commit") or {}).get("author") or {}).get("date", ""),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def create_pr(branch: str, title: str, body: str) -> dict:
    ok, out = _gh("pr", "create", "--head", branch, "--base", "main", "--title", title, "--body", body)
    if not ok:
        return {"ok": False, "error": out}
    # gh pr create returns the PR URL on success
    pr_url = out.strip()
    pr_number = None
    if "/pull/" in pr_url:
        try:
            pr_number = int(pr_url.rstrip("/").split("/")[-1])
        except Exception:
            pass
    return {"ok": True, "url": pr_url, "number": pr_number}


def auto_merge_pr(pr_number: int) -> dict:
    ok, out = _gh("pr", "merge", str(pr_number), "--squash", "--admin", "--delete-branch")
    return {"ok": ok, "output": out}


def close_pr(pr_number: int, reason: str = "") -> bool:
    ok, _ = _gh("pr", "close", str(pr_number), "--comment", reason or "Closed by CTO agent")
    return ok
