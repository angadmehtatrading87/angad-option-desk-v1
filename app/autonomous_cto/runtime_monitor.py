from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

SSH_KEY = "~/Downloads/LightsailDefaultKey-eu-west-2.pem"
SSH_HOST = "ubuntu@16.60.74.15"
SSH_OPTS = ["-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=15"]

CORE_SERVICES = ["ig-execution-worker", "angad-option-desk", "telegram-control-room"]
ALL_SERVICES = [
    "ig-execution-worker",
    "angad-option-desk",
    "telegram-control-room",
    "angad-ig-briefing",
    "angad-daily-learning",
    "autonomous-cto",
]


def _ssh(cmd: str, timeout: int = 30) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["ssh"] + SSH_OPTS + [SSH_HOST, cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return False, "ssh_timeout"
    except Exception as e:
        return False, str(e)


def check_service_health() -> dict:
    statuses: dict[str, str] = {}
    checks = " && ".join(
        f'echo "{svc}:$(systemctl is-active {svc} 2>/dev/null || echo unknown)"'
        for svc in ALL_SERVICES
    )
    ok, output = _ssh(checks)
    if not ok:
        return {
            "ok": False,
            "score": 0.0,
            "services": {s: "ssh_unreachable" for s in ALL_SERVICES},
            "degraded": ALL_SERVICES,
            "critical": CORE_SERVICES,
            "ssh_error": output,
        }

    for line in output.splitlines():
        if ":" in line:
            svc, _, state = line.partition(":")
            statuses[svc.strip()] = state.strip()

    for svc in ALL_SERVICES:
        if svc not in statuses:
            statuses[svc] = "unknown"

    degraded = [s for s, st in statuses.items() if st != "active"]
    critical = [s for s in CORE_SERVICES if statuses.get(s) != "active"]
    score = compute_health_score(statuses)

    return {
        "ok": True,
        "score": score,
        "services": statuses,
        "degraded": degraded,
        "critical": critical,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def compute_health_score(service_statuses: dict[str, str]) -> float:
    total = 0.0
    earned = 0.0
    weights = {s: 3.0 for s in CORE_SERVICES}
    for s in ALL_SERVICES:
        w = weights.get(s, 1.0)
        total += w
        if service_statuses.get(s) == "active":
            earned += w
    return round((earned / total) * 100, 1) if total > 0 else 0.0


def get_recent_worker_logs(service: str, lines: int = 50) -> str:
    ok, output = _ssh(f"sudo journalctl -u {service} -n {lines} --no-pager -o cat 2>/dev/null")
    return output if ok else f"[log fetch failed: {output}]"


def get_deployed_sha() -> str:
    ok, output = _ssh("cd ~/angad-option-desk-v1 && git rev-parse --short HEAD 2>/dev/null")
    return output.strip() if ok else "unknown"
