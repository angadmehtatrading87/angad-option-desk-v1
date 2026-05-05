"""
Daily code-proposer orchestration.

Per-day flow:
    1. Read config/agent_proposer.yaml
    2. Collect state via state_collector.collect_state_pack()
    3. Build the prompt
    4. Call LLM (cost-capped)
    5. Parse the response
    6. Validate (forbidden paths, diff size)
    7. Deliver via Telegram (v1) and/or open PR (v2)

This module is the orchestration layer. The actual LLM call is in
`llm_client.py`, the prompt in `proposal_prompt.py`, the state collection
in `state_collector.py`. This keeps each piece independently testable.
"""

from __future__ import annotations

import json
import os
import re
import textwrap
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from app.agent_ops.llm_client import LLMClient, LLMUnavailable, LLMResponse
from app.agent_ops.proposal_prompt import build_prompt
from app.agent_ops.state_collector import collect_state_pack

DXB = ZoneInfo("Asia/Dubai")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "agent_proposer.yaml")
LOG_DIR = os.path.join(BASE_DIR, "data", "agent_proposals")


@dataclass
class Proposal:
    title: str
    rationale: str
    diff: str
    test_hint: str
    confidence: str
    risk_notes: str
    raw_response: str
    rejected_reason: str | None = None


def _load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f) or {}


def _now_iso() -> str:
    return datetime.now(DXB).isoformat()


def _save_proposal_log(payload: dict) -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    fname = f"{datetime.now(DXB).strftime('%Y%m%d_%H%M')}.json"
    path = os.path.join(LOG_DIR, fname)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    return path


def _extract_json_block(text: str) -> dict | None:
    """Pull the first ```json ... ``` fenced block out of an LLM response.
    Returns None if not found or unparseable."""
    m = re.search(r"```json\s*(.+?)```", text, flags=re.DOTALL)
    if not m:
        # Try without language hint
        m = re.search(r"```\s*(\{.+?\})\s*```", text, flags=re.DOTALL)
    if not m:
        return None
    raw = m.group(1).strip()
    try:
        return json.loads(raw)
    except Exception:
        return None


def _diff_line_count(diff: str) -> int:
    """Count + and - lines (excluding ---/+++ headers)."""
    if not diff:
        return 0
    n = 0
    for ln in diff.split("\n"):
        if ln.startswith("+++") or ln.startswith("---"):
            continue
        if ln.startswith("+") or ln.startswith("-"):
            n += 1
    return n


def _diff_touches_forbidden(diff: str, forbidden_paths: list[str]) -> str | None:
    """If the diff modifies any forbidden path, return the offending path."""
    # Look at +++/--- file headers in the diff
    for ln in diff.split("\n"):
        if not (ln.startswith("+++ ") or ln.startswith("--- ")):
            continue
        # Format: "+++ b/path/to/file"
        path = ln[4:].strip()
        if path.startswith("a/") or path.startswith("b/"):
            path = path[2:]
        for forbidden in forbidden_paths:
            if path == forbidden or path.startswith(forbidden.rstrip("/") + "/"):
                return path
    return None


def _validate_proposal(parsed: dict, cfg: dict) -> Proposal:
    """Build a Proposal object from parsed JSON, marking it rejected if
    it violates any constraint."""
    diff = str(parsed.get("diff") or "")
    forbidden = cfg.get("forbidden_paths", []) or []
    max_lines = int(cfg.get("max_diff_lines", 200))

    rejected = None
    n_lines = _diff_line_count(diff)
    if n_lines > max_lines:
        rejected = f"diff_too_large ({n_lines} > {max_lines})"
    if not rejected:
        offending = _diff_touches_forbidden(diff, forbidden)
        if offending:
            rejected = f"forbidden_path:{offending}"
    if not rejected and not diff.strip():
        rejected = "empty_diff"

    return Proposal(
        title=str(parsed.get("title") or "")[:200],
        rationale=str(parsed.get("rationale") or ""),
        diff=diff,
        test_hint=str(parsed.get("test_hint") or ""),
        confidence=str(parsed.get("confidence") or "low").lower(),
        risk_notes=str(parsed.get("risk_notes") or ""),
        raw_response="",
        rejected_reason=rejected,
    )


def _format_telegram_message(proposal: Proposal, cfg: dict) -> str:
    """Render the proposal as a Telegram-friendly HTML string."""
    fmt = cfg.get("telegram_format", {}) or {}
    truncate = int(fmt.get("truncate_diff_above_lines", 80))

    diff_block = proposal.diff
    if proposal.diff:
        diff_lines = proposal.diff.split("\n")
        if len(diff_lines) > truncate:
            kept = diff_lines[:truncate]
            diff_block = "\n".join(kept) + f"\n... (truncated; {len(diff_lines) - truncate} more lines, see data/agent_proposals/)"

    parts = []
    parts.append(f"<b>🧠 Daily Improvement Proposal</b>")
    parts.append(f"<i>{_now_iso()}</i>")
    parts.append("")
    parts.append(f"<b>{proposal.title}</b>")
    parts.append(f"Confidence: {proposal.confidence}")
    parts.append("")
    if proposal.rationale and fmt.get("include_rationale", True):
        parts.append(f"<b>Why</b>")
        parts.append(proposal.rationale)
        parts.append("")
    if proposal.risk_notes:
        parts.append(f"<b>Risk</b>")
        parts.append(proposal.risk_notes)
        parts.append("")
    if proposal.test_hint:
        parts.append(f"<b>Validate by</b> {proposal.test_hint}")
        parts.append("")
    if fmt.get("include_full_diff", True) and diff_block:
        parts.append(f"<b>Diff</b>")
        parts.append("<pre>")
        parts.append(diff_block)
        parts.append("</pre>")
        parts.append("")
    parts.append("<i>Reply in chat to discuss / accept / reject.</i>")
    return "\n".join(parts)


def _format_telegram_no_proposal(state_pack: dict) -> str:
    trades = state_pack.get("trades_24h", {}) or {}
    errors = state_pack.get("errors_24h", []) or []
    cost = state_pack.get("cost_cap", {}) or {}
    plan = state_pack.get("current_plan", {}) or {}
    regime = (plan.get("regime") or {}).get("regime", "—")
    return "\n".join([
        f"<b>🧠 Daily Improvement Proposal — None today</b>",
        f"<i>{_now_iso()}</i>",
        "",
        f"Trades attempted (24h): {trades.get('submitted_count_24h', 0)}",
        f"Errors logged (24h): {len(errors)}",
        f"Current regime: {regime}",
        f"LLM USD spent today: ${cost.get('rows', [{}])[-1].get('used', 0) if cost.get('rows') else 0}",
        "",
        "<i>Bot looks healthy and there's no clear improvement to suggest. Will check again tomorrow 02:00 Dubai.</i>",
    ])


def _send_telegram(message: str) -> dict:
    try:
        from app.telegram_alerts import send_telegram_message
        send_telegram_message(message)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def run_one_proposal_cycle() -> dict:
    """Top-level: collect state, ask Claude, deliver. Returns a dict
    suitable for logging."""
    cfg = _load_config()
    if not cfg:
        return {"ok": False, "stage": "config", "error": "no agent_proposer.yaml"}

    state_pack = collect_state_pack()
    system, user = build_prompt(
        state_pack=state_pack,
        forbidden_paths=cfg.get("forbidden_paths", []),
        max_diff_lines=int(cfg.get("max_diff_lines", 200)),
    )

    client = LLMClient(model=cfg.get("model", "claude-sonnet-4-6"))
    try:
        response: LLMResponse = client.complete(
            system=system,
            user=user,
            max_output_tokens=int(cfg.get("max_output_tokens", 4000)),
            temperature=0.2,
        )
    except LLMUnavailable as e:
        log = {
            "ts": _now_iso(),
            "ok": False,
            "stage": "llm_call",
            "error": str(e),
            "state_pack_keys": list(state_pack.keys()),
        }
        _save_proposal_log(log)
        return log

    raw = response.text.strip()

    # Did Claude opt out?
    if raw == "NO_PROPOSAL":
        if cfg.get("delivery", {}).get("telegram", True):
            _send_telegram(_format_telegram_no_proposal(state_pack))
        log = {
            "ts": _now_iso(),
            "ok": True,
            "stage": "no_proposal",
            "model": response.model,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "usd_cost": response.usd_cost,
        }
        _save_proposal_log(log)
        return log

    parsed = _extract_json_block(raw)
    if not parsed:
        log = {
            "ts": _now_iso(),
            "ok": False,
            "stage": "parse",
            "error": "no JSON block in response",
            "raw_truncated": raw[:1000],
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "usd_cost": response.usd_cost,
        }
        _save_proposal_log(log)
        return log

    proposal = _validate_proposal(parsed, cfg)
    proposal.raw_response = raw

    if proposal.rejected_reason:
        log = {
            "ts": _now_iso(),
            "ok": False,
            "stage": "validate",
            "rejected_reason": proposal.rejected_reason,
            "title": proposal.title,
            "diff_lines": _diff_line_count(proposal.diff),
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "usd_cost": response.usd_cost,
        }
        _save_proposal_log(log)
        return log

    if cfg.get("delivery", {}).get("telegram", True):
        _send_telegram(_format_telegram_message(proposal, cfg))

    # TODO v2: if cfg.delivery.github_pr → apply diff + push branch + open PR

    log = {
        "ts": _now_iso(),
        "ok": True,
        "stage": "delivered",
        "delivery": {"telegram": cfg.get("delivery", {}).get("telegram", True)},
        "title": proposal.title,
        "confidence": proposal.confidence,
        "diff_lines": _diff_line_count(proposal.diff),
        "rationale": proposal.rationale[:500],
        "raw_response_len": len(raw),
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "usd_cost": response.usd_cost,
    }
    _save_proposal_log(log)
    return log
