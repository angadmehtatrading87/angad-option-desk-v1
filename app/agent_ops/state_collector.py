"""
Daily state collector for the code-proposer.

Builds a compact snapshot of the bot's last 24h of operation that gets
fed into the LLM prompt. Designed to be:

    1. Small (token-budget-sensitive)
    2. Information-dense (only stuff Claude can actually act on)
    3. Free of credentials, IPs, account IDs (we never paste secrets to LLMs)

Returns a dict that the prompt builder serializes to YAML/JSON.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

DXB = ZoneInfo("Asia/Dubai")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Pattern that matches values we never want to include in the LLM prompt.
SECRET_PATTERN = re.compile(
    r"(api[_-]?key|password|secret|token|credential|client[_-]?id|cst|x-security)",
    re.IGNORECASE,
)


def _redact(value: Any) -> Any:
    """Recursively scrub anything that looks like a secret key."""
    if isinstance(value, dict):
        return {
            k: ("[REDACTED]" if SECRET_PATTERN.search(str(k)) else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _now() -> datetime:
    return datetime.now(DXB)


def _safe_load_json(path: str, default=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default


def _git_state() -> dict:
    out: dict[str, Any] = {}
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=5
        )
        out["head_sha"] = head.stdout.strip()
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=5
        )
        out["branch"] = branch.stdout.strip()
        log = subprocess.run(
            ["git", "log", "-10", "--pretty=format:%h %s", "--no-merges"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=5
        )
        out["recent_commits"] = log.stdout.strip().split("\n")
        files = subprocess.run(
            ["git", "log", "--since=7.days", "--name-only", "--pretty=format:"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=5
        )
        changed = sorted(set([f.strip() for f in files.stdout.split("\n") if f.strip()]))
        out["files_changed_last_7d"] = changed[:50]
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def _trades_24h(limit: int = 100) -> dict:
    out: dict[str, Any] = {"submitted": [], "skip_reasons_summary": {}}
    try:
        from app.ig_trade_store import recent_ig_trade_log
        rows = recent_ig_trade_log(limit=limit) or []
    except Exception as e:
        out["error"] = f"trade log unavailable: {e}"
        return out

    cutoff = _now() - timedelta(hours=24)
    cutoff_iso = cutoff.isoformat()

    today_rows = []
    for row in rows:
        ts = str(row.get("created_at") or row.get("ts") or "")
        if ts < cutoff_iso:
            continue
        # strip noisy fields, keep what's actionable
        compact = {
            "epic": row.get("epic"),
            "direction": row.get("direction"),
            "status": row.get("status"),
            "confidence": row.get("confidence"),
            "score": row.get("score"),
            "ts": ts,
        }
        today_rows.append(compact)

    out["submitted_count_24h"] = len(today_rows)
    out["recent"] = today_rows[:30]
    return out


def _journal_recent_errors(lines: int = 80) -> list[str]:
    """Pull recent error lines from journalctl. Best-effort — silently
    returns empty if journalctl is not available (e.g. dev box)."""
    try:
        result = subprocess.run(
            [
                "journalctl",
                "-u", "ig-execution-worker",
                "--since", "24 hours ago",
                "--no-pager",
                "-n", str(lines),
            ],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return []

    out = []
    for ln in result.stdout.split("\n"):
        if not ln.strip():
            continue
        # only keep lines that look like JSON errors or python tracebacks
        if '"ok": false' in ln or "Traceback" in ln or "Error" in ln or "exception" in ln.lower():
            # Trim ridiculously long lines
            out.append(ln[:1200])
    # Collapse repeats — most error logs spam the same exception
    counter = Counter(out)
    deduped = []
    for line, count in counter.most_common(20):
        if count > 1:
            deduped.append(f"({count}x) {line}")
        else:
            deduped.append(line)
    return deduped


def _cost_cap_state() -> dict:
    try:
        from app.cost_cap_meter import snapshot
        return snapshot()
    except Exception as e:
        return {"error": str(e)}


def _v2_plan_summary() -> dict:
    """Run the orchestrator once to capture the current decision state."""
    try:
        from app.agent_v2_orchestrator import build_agent_v2_plan
        plan = build_agent_v2_plan() or {}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

    out: dict[str, Any] = {
        "ok": plan.get("ok"),
        "regime": plan.get("regime"),
        "deployment": plan.get("deployment"),
        "loss_governor": plan.get("loss_governor"),
        "candidate_count": len(plan.get("candidates") or []),
        "candidates": [
            {
                "symbol": c.get("symbol"),
                "direction": c.get("direction"),
                "score": c.get("score"),
                "confidence": c.get("confidence"),
                "structure_bias": (c.get("structure") or {}).get("bias"),
            }
            for c in (plan.get("candidates") or [])[:5]
        ],
        "ranked_below_threshold": [
            {"symbol": r.get("symbol"), "score": r.get("total_score")}
            for r in (plan.get("ranked") or [])[:10]
        ],
        "mtf_diagnostics": {
            epic: {
                "degraded": (d or {}).get("degraded"),
                "available_count": (d or {}).get("available_count"),
            }
            for epic, d in (plan.get("mtf_diagnostics") or {}).items()
        },
    }
    return _redact(out)


def collect_state_pack() -> dict:
    return _redact({
        "today_dubai": _now().isoformat(),
        "git": _git_state(),
        "trades_24h": _trades_24h(),
        "errors_24h": _journal_recent_errors(),
        "cost_cap": _cost_cap_state(),
        "current_plan": _v2_plan_summary(),
    })
