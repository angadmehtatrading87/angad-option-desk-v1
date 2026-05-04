from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_DB_TABLES = {
    "ig_trade_log",
    "virtual_equity_log",
    "virtual_account",
    "virtual_positions",
    "trade_proposals",
    "learning_log",
}


@dataclass
class FactoryPaths:
    repo: Path

    @property
    def reports(self) -> Path:
        return self.repo / "reports"

    @property
    def data(self) -> Path:
        return self.repo / "data"


def _run(cmd: str, cwd: Path) -> dict[str, Any]:
    p = subprocess.run(cmd, cwd=cwd, shell=True, text=True, capture_output=True)
    return {"cmd": cmd, "rc": p.returncode, "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}


def github_repo_manager(repo: Path) -> dict[str, Any]:
    return {
        "git_status": _run("git status --short --branch", repo),
        "current_branch": _run("git rev-parse --abbrev-ref HEAD", repo),
        "latest_commit": _run("git log -1 --oneline", repo),
        "changed_files": _run("git diff --name-only", repo),
        "merge_status": _run("git status --porcelain", repo),
        "conflicts": _run("git diff --name-only --diff-filter=U", repo),
    }


def generate_codex_improvement_brief(repo: Path) -> Path:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = repo / "reports" / f"codex_improvement_brief_{today}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    git = github_repo_manager(repo)
    body = [
        f"# Codex Improvement Brief ({today})",
        "",
        "## Bug diagnosis prompt",
        "Diagnose regressions using latest failing tests and runtime errors.",
        "",
        "## PR acceptance criteria",
        "- All telegram control room commands route correctly.",
        "- Weekend deploy requires explicit approval.",
        "- No secrets in generated reports.",
        "",
        "## Test plan",
        "Run compile, pytest subset, systemd validation, and smoke status commands.",
        "",
        "## Deployment fix prompt",
        "If deploy fails, capture failing step, rollback, and summarize remediation.",
        "",
        "## Trading performance improvement prompt",
        "Prioritize fewer high-conviction allocations and reduce low-quality churn.",
        "",
        "## Weekly backlog (priority scored)",
        f"1. Stabilize failing CI paths (score 10)\n2. Harden deployment rollback notes (score 9)\n3. Expand report coverage (score 8)",
        "",
        "## Repo snapshot",
        f"```json\n{json.dumps(git, indent=2)[:3000]}\n```",
    ]
    out.write_text("\n".join(body))
    return out


def validate_systemd_units(repo: Path) -> dict[str, Any]:
    unit_dir = repo / "deploy" / "systemd"
    result = {}
    for p in sorted(unit_dir.glob("*.service")):
        txt = p.read_text()
        result[p.name] = {
            "has_execstart": "ExecStart=" in txt,
            "has_install": "[Install]" in txt,
        }
    return result


def db_schema_inspector(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {"exists": False, "missing_tables": sorted(REQUIRED_DB_TABLES)}
    con = sqlite3.connect(db_path)
    try:
        names = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    finally:
        con.close()
    return {"exists": True, "missing_tables": sorted(REQUIRED_DB_TABLES - names), "present_tables": sorted(names)}


def redact_secrets(text: str) -> str:
    text = re.sub(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s]+", r"\1=[REDACTED]", text)
    return text


def build_factory_health(repo: Path) -> dict[str, Any]:
    paths = FactoryPaths(repo)
    paths.reports.mkdir(exist_ok=True)
    db = db_schema_inspector(paths.data / "trades.db")
    systemd = validate_systemd_units(repo)
    git = github_repo_manager(repo)
    brief = generate_codex_improvement_brief(repo)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "factory_health": "ok",
        "github": git,
        "db": db,
        "systemd": systemd,
        "codex_improvement_brief": str(brief),
        "next_recommended_action": "stabilize-first" if db.get("missing_tables") else "continue",
    }


def write_factory_report(repo: Path) -> Path:
    payload = build_factory_health(repo)
    out = Path(repo) / "reports" / "latest_factory_report.json"
    out.write_text(json.dumps(payload, indent=2))
    return out
