from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone

from app.autonomous_cto import policy_engine

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _git(*args: str, timeout: int = 30) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["git"] + list(args),
            capture_output=True, text=True, timeout=timeout, cwd=BASE_DIR,
        )
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


def create_branch(branch_name: str) -> bool:
    ok, _ = _git("checkout", "main")
    if not ok:
        _git("checkout", "-")  # try returning to whatever branch we were on
    ok, out = _git("checkout", "-b", branch_name)
    return ok


def apply_patch(patch: dict) -> tuple[bool, str]:
    filepath = patch.get("file", "")
    old_snippet = patch.get("old_snippet", "").strip()
    new_snippet = patch.get("new_snippet", "")

    allowed, reason = policy_engine.file_patch_allowed(filepath)
    if not allowed:
        return False, f"policy rejected patch to {filepath}: {reason}"

    full_path = os.path.join(BASE_DIR, filepath)
    if not os.path.exists(full_path):
        return False, f"file not found: {full_path}"

    try:
        with open(full_path, "r") as f:
            content = f.read()
    except Exception as e:
        return False, f"read error: {e}"

    if old_snippet and old_snippet != "NONE":
        if old_snippet in content:
            new_content = content.replace(old_snippet, new_snippet, 1)
        else:
            # Fallback: strip trailing whitespace per line and retry
            def _norm(s: str) -> str:
                return "\n".join(ln.rstrip() for ln in s.splitlines())
            norm_old = _norm(old_snippet)
            norm_content = _norm(content)
            if norm_old not in norm_content:
                return False, f"old_snippet not found in {filepath} (may already be patched or stale)"
            # Splice by finding the byte range in the original content
            idx = norm_content.find(norm_old)
            lines_before = norm_content[:idx].count("\n")
            snippet_line_count = norm_old.count("\n") + 1
            orig_lines = content.splitlines(keepends=True)
            start = sum(len(orig_lines[i]) for i in range(lines_before))
            end = sum(len(orig_lines[i]) for i in range(lines_before + snippet_line_count))
            new_content = content[:start] + new_snippet + ("\n" if not new_snippet.endswith("\n") else "") + content[end:]
    else:
        # Append to end of file
        new_content = content.rstrip("\n") + "\n\n" + new_snippet + "\n"

    try:
        with open(full_path, "w") as f:
            f.write(new_content)
        return True, f"patched {filepath}"
    except Exception as e:
        return False, f"write error: {e}"


def apply_patch_plan(patches: list[dict], branch_name: str) -> dict:
    if not patches:
        return {"ok": False, "error": "no patches to apply"}

    if not create_branch(branch_name):
        return {"ok": False, "error": f"failed to create branch {branch_name}"}

    results = []
    all_ok = True
    for patch in patches:
        ok, msg = apply_patch(patch)
        results.append({"file": patch.get("file"), "ok": ok, "msg": msg})
        if not ok:
            all_ok = False

    if not all_ok:
        # Abort — switch back to main and delete branch
        _git("checkout", "main")
        _git("branch", "-D", branch_name)
        return {"ok": False, "error": "one or more patches failed", "results": results}

    commit_ok = commit_patches(branch_name, f"cto: auto-patch — {patches[0].get('description', 'improvement')[:60]}")
    return {"ok": commit_ok, "branch": branch_name, "results": results}


def commit_patches(branch_name: str, message: str) -> bool:
    _git("add", "-A")
    ok, out = _git("commit", "-m", message)
    if not ok:
        return False
    ok, out = _git("push", "origin", branch_name)
    return ok
