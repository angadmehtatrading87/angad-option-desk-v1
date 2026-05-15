from __future__ import annotations

from app.autonomous_cto import claude_worker, openai_worker


def _try(primary_fn, fallback_fn, prompt: str, system: str, max_tokens: int = 4000) -> dict:
    result = primary_fn(prompt=prompt, system=system, max_tokens=max_tokens)
    if result.get("ok"):
        return result
    # Primary failed — try fallback
    fallback = fallback_fn(prompt=prompt, system=system, max_tokens=max_tokens)
    if fallback.get("ok"):
        fallback["fallback"] = True
        return fallback
    return {"ok": False, "text": "", "error": f"both providers failed: {result.get('error')} / {fallback.get('error')}", "cost_usd": 0.0}


def route_code_patch(prompt: str, system: str, max_tokens: int = 6000) -> dict:
    """Claude first (better at code), OpenAI fallback."""
    return _try(
        lambda **kw: claude_worker.complete(**kw, model="claude-sonnet-4-6"),
        lambda **kw: openai_worker.complete(**kw, model="gpt-4o"),
        prompt=prompt,
        system=system,
        max_tokens=max_tokens,
    )


def route_diagnosis(prompt: str, system: str, max_tokens: int = 2000) -> dict:
    """OpenAI first for structured analysis, Claude fallback."""
    return _try(
        lambda **kw: openai_worker.complete(**kw, model="gpt-4o"),
        lambda **kw: claude_worker.complete(**kw, model="claude-sonnet-4-6"),
        prompt=prompt,
        system=system,
        max_tokens=max_tokens,
    )


def route_review(prompt: str, system: str, max_tokens: int = 2000) -> dict:
    """OpenAI preferred for review/critique tasks."""
    return _try(
        lambda **kw: openai_worker.complete(**kw, model="gpt-4o"),
        lambda **kw: claude_worker.complete(**kw, model="claude-haiku-4-5-20251001"),
        prompt=prompt,
        system=system,
        max_tokens=max_tokens,
    )


def route_quick(prompt: str, system: str, max_tokens: int = 500) -> dict:
    """Cheapest model for classification/short tasks."""
    return _try(
        lambda **kw: claude_worker.complete(**kw, model="claude-haiku-4-5-20251001"),
        lambda **kw: openai_worker.complete(**kw, model="gpt-4o-mini"),
        prompt=prompt,
        system=system,
        max_tokens=max_tokens,
    )
