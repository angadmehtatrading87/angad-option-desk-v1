from __future__ import annotations

import re
from typing import Any

from app.autonomous_cto import llm_router

_SYSTEM = """You are the autonomous CTO engineer for a live FX trading bot built in Python.
Your job: given a diagnosis of what is wrong, produce minimal, safe, targeted code patches.

Output ONLY valid patch blocks in this exact XML format — no prose, no explanation outside the tags:

<patch>
  <file>app/relative/path.py</file>
  <description>One-line description of what changes and why</description>
  <old_snippet>EXACT text to find and replace in the file (multi-line ok). Write NONE if inserting at end.</old_snippet>
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


def plan_patch_for_issue(issue: dict, diagnosis: dict) -> dict:
    from app.autonomous_cto.diagnostics_engine import format_diagnosis_for_llm
    diagnosis_text = format_diagnosis_for_llm(diagnosis)

    prompt = f"""ISSUE TO FIX:
severity: {issue.get('severity')}
area: {issue.get('area')}
issue: {issue.get('issue')}
suggested_action: {issue.get('suggested_action')}

FULL SYSTEM DIAGNOSIS:
{diagnosis_text}

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
