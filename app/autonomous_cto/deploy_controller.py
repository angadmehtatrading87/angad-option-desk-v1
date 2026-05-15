from __future__ import annotations

import os
import re
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEPLOY_SCRIPT = os.path.join(BASE_DIR, "push-and-deploy.sh")


def deploy(commit_message: str = "cto: auto-deploy") -> dict:
    try:
        r = subprocess.run(
            [DEPLOY_SCRIPT, commit_message],
            capture_output=True, text=True, timeout=240, cwd=BASE_DIR,
        )
        output = r.stdout + r.stderr
        deployed_sha = _extract_sha(output)
        return {
            "ok": r.returncode == 0,
            "deployed_sha": deployed_sha,
            "output": output[-2000:],
            "returncode": r.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "deployed_sha": "", "output": "deploy timed out after 240s", "returncode": -1}
    except Exception as e:
        return {"ok": False, "deployed_sha": "", "output": str(e), "returncode": -1}


def _extract_sha(output: str) -> str:
    # push-and-deploy.sh prints "local main:    <sha>"
    m = re.search(r"local main:\s+([0-9a-f]{6,})", output)
    if m:
        return m.group(1)
    return ""
