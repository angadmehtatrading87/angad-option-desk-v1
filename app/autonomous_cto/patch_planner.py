from __future__ import annotations

import os
import re
from typing import Any

from app.autonomous_cto import llm_router

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Files most likely to need patching, included verbatim so the LLM can
# copy exact old_snippets rather than guessing from training data.
_CORE_FILES = [
    "app/market_brain_execution_bridge.py",
    "app/market_brain_engines.py",
    "app/execution_safety_guard.py",
    "config/cto_policy.json",
    "config/risk_limits.yaml",
]

_SYSTEM = """You are the autonomous CTO engineer for a live FX trading bot built in Python.
Your job: given a diagnosis of what is wrong, produce minimal, safe, targeted code patches.

CRITICAL: The prompt includes the EXACT current content of key files. You MUST copy the
old_snippet character-for-character from those file contents — do not paraphrase or reconstruct
from memory. If you cannot find an exact match for what you want to change, output <no_patch_needed/>.

Output ONLY valid patch blocks in this exact XML format — no prose, no explanation outside the tags:

<patch>
  <file>app/relative/path.py</file>
  <description>One-line description of what changes and why</description>
  <old_snippet>EXACT text copied verbatim from the file listing below</old_snippet>
  <new_snippet>Replacement text that will overwrite old_snippet</new_snippet>
</patch>

Rules:
- Only patch files under app/ or config/ — never push-and-deploy.sh, .github/, deploy/systemd/
- Each patch must be a minimal targeted change (not a rewrite)
- Preserve indentation and code style exactly
- If a config value (env var threshold), change only config/cto_policy.json or document the env var to update
- Never remove safety guards or kill-switches
- Never touch TastyTrade tables or legacy code
- If no patch is needed, output: <no_patch_needed/>"""


def _read_file_for_context(rel_path: str, max_lines: int = 120) -> str:
    full = os.path.join(BASE_DIR, rel_path)
    try:
        with open(full) as f:
            lines = f.readlines()
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines.append(f"... [{len(lines)} lines truncated] ...\n")
        return "".join(lines)
    except Exception:
        return ""


def _build_file_context() -> str:
    parts = []
    for rel in _CORE_FILES:
        content = _read_file_for_context(rel)
        if content:
            parts.append(f"=== FILE: {rel} ===\n{content}\n")
    return "\n".join(parts)


def plan_patch_for_issue(issue: dict, diagnosis: dict) -> dict:
    from app.autonomous_cto.diagnostics_engine import format_diagnosis_for_llm
    diagnosis_text = format_diagnosis_for_llm(diagnosis)
    file_context = _build_file_context()

    prompt = f"""ISSUE TO FIX:
severity: {issue.get('severity')}
area: {issue.get('area')}
issue: {issue.get('issue')}
suggested_action: {issue.get('suggested_action')}

FULL SYSTEM DIAGNOSIS:
{diagnosis_text}

CURRENT FILE CONTENTS (copy old_snippet EXACTLY from these):
{file_context}

Produce the minimal code patch(es) to address this issue. Output only <patch> XML blocks."""

    result = llm_router.route_code_patch(prompt=prompt, system=_SYSTEM, max_tokens=6000)
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error"), "patches": []}

    patches = parse_patch_plan(result["text"])
    return {
        "ok": True,
        "patches": patches,
        "llm_text": result["text"],
        "provider": result.get("model", "unknown"),
        "cost_usd": result.get("cost_usd", 0.0),
    }


def parse_patch_plan(llm_response: str) -> list[dict]:
    if "<no_patch_needed/>" in llm_response:
        return []

    patches = []
    for block in re.finditer(r"<patch>(.*?)</patch>", llm_response, re.DOTALL):
        xml = block.group(1)
        patch: dict[str, Any] = {}
        for tag in ("file", "description", "old_snippet", "new_snippet"):
            m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.DOTALL)
            patch[tag] = m.group(1).strip() if m else ""
        if patch.get("file") and patch.get("new_snippet"):
            patches.append(patch)

    return patches
