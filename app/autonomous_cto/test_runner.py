from __future__ import annotations

import os
import re
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_tests(test_path: str = "tests/", timeout: int = 300) -> dict:
    start = time.time()
    try:
        r = subprocess.run(
            ["python3", "-m", "pytest", test_path, "-x", "--tb=short", "-q", "--no-header"],
            capture_output=True, text=True, timeout=timeout,
            cwd=BASE_DIR,
        )
        output = r.stdout + r.stderr
        passed, failed, errors = _parse_pytest_output(output)
        return {
            "ok": r.returncode == 0,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "output": output[-3000:],  # last 3k chars for logging
            "duration": round(time.time() - start, 1),
            "returncode": r.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "passed": 0,
            "failed": 0,
            "errors": 1,
            "output": "pytest timed out",
            "duration": timeout,
            "returncode": -1,
        }
    except Exception as e:
        return {
            "ok": False,
            "passed": 0,
            "failed": 0,
            "errors": 1,
            "output": str(e),
            "duration": round(time.time() - start, 1),
            "returncode": -1,
        }


def _parse_pytest_output(output: str) -> tuple[int, int, int]:
    passed = failed = errors = 0
    # "3 passed", "2 failed", "1 error" in summary line
    for m in re.finditer(r"(\d+) (passed|failed|error)", output):
        n, kind = int(m.group(1)), m.group(2)
        if kind == "passed":
            passed = n
        elif kind == "failed":
            failed = n
        elif kind == "error":
            errors = n
    return passed, failed, errors
