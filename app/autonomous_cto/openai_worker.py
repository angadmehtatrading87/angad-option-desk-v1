from __future__ import annotations

import json
import os

import requests

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

# Pricing per million tokens (input, output)
_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
}


def _is_killed() -> bool:
    try:
        from app.cost_cap_meter import is_killed
        return is_killed("llm_calls_killed")
    except Exception:
        return False


def _record(category: str, amount: float) -> None:
    try:
        from app.cost_cap_meter import record
        record(category, amount)
    except Exception:
        pass


def _cost(model: str, in_tok: int, out_tok: int) -> float:
    in_p, out_p = _PRICING.get(model, (5.0, 15.0))
    return (in_tok / 1_000_000) * in_p + (out_tok / 1_000_000) * out_p


def complete(
    prompt: str,
    system: str,
    model: str = "gpt-4o",
    max_tokens: int = 4000,
) -> dict:
    if _is_killed():
        return {"ok": False, "text": "", "error": "llm_calls_killed", "cost_usd": 0.0}

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return {"ok": False, "text": "", "error": "OPENAI_API_KEY not set", "cost_usd": 0.0}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    try:
        r = requests.post(OPENAI_API_URL, headers=headers, json=payload, timeout=120)
    except requests.exceptions.Timeout as e:
        return {"ok": False, "text": "", "error": f"timeout: {e}", "cost_usd": 0.0}
    except Exception as e:
        return {"ok": False, "text": "", "error": str(e), "cost_usd": 0.0}

    if not r.ok:
        return {"ok": False, "text": "", "error": f"HTTP {r.status_code}: {r.text[:200]}", "cost_usd": 0.0}

    try:
        body = r.json()
    except Exception as e:
        return {"ok": False, "text": "", "error": f"non-JSON: {e}", "cost_usd": 0.0}

    text = (body.get("choices") or [{}])[0].get("message", {}).get("content", "")
    usage = body.get("usage") or {}
    in_tok = int(usage.get("prompt_tokens") or 0)
    out_tok = int(usage.get("completion_tokens") or 0)
    cost = _cost(model, in_tok, out_tok)

    _record("llm_tokens", float(in_tok + out_tok))
    _record("llm_usd", cost)

    return {
        "ok": True,
        "text": text,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": cost,
        "model": model,
    }
