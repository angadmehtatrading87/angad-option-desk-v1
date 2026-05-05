"""
Cost-capped Anthropic Claude client.

This is the SINGLE place LLM calls happen in the codebase. Every call is:
    1. Gated by the kill-switch (`is_killed("llm_calls_killed")`)
    2. Pre-checked against the per-day budget
    3. Metered post-call (tokens used + USD spent)
    4. Logged

Caller pattern:

    from app.agent_ops.llm_client import LLMClient, LLMUnavailable
    client = LLMClient()
    try:
        response = client.complete(
            system="...",
            user="...",
            max_output_tokens=4000,
        )
    except LLMUnavailable as e:
        # cap hit, kill-switch on, or no API key — log and skip
        ...

If `ANTHROPIC_API_KEY` is unset, the client raises `LLMUnavailable` on
first call. This is intentional: we never silently fall back to "fake"
responses for safety-critical reasoning.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

# Pricing as of mid-2025 (Anthropic public list). Updated when significant
# pricing changes happen — these numbers feed the cost-cap meter, so
# accuracy matters.
PRICING_USD_PER_MTOK = {
    # model_id: (input_per_million, output_per_million)
    "claude-sonnet-4-6":  (3.0, 15.0),
    "claude-opus-4-6":    (15.0, 75.0),
    "claude-haiku-4-5-20251001": (0.80, 4.0),
}


class LLMUnavailable(Exception):
    """Raised when the LLM cannot be called: no key, kill-switch, or cap reached."""


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    usd_cost: float
    model: str
    stop_reason: str | None


class LLMClient:
    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model
        self.api_key = os.getenv("ANTHROPIC_API_KEY") or ""

    def _is_killed(self) -> bool:
        try:
            from app.cost_cap_meter import is_killed
            return is_killed("llm_calls_killed")
        except Exception:
            return False

    def _record(self, category: str, amount: float) -> None:
        try:
            from app.cost_cap_meter import record
            record(category, amount)
        except Exception:
            pass

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        prices = PRICING_USD_PER_MTOK.get(self.model)
        if not prices:
            # Conservative default if model is unknown
            return (input_tokens / 1_000_000) * 5.0 + (output_tokens / 1_000_000) * 25.0
        in_price, out_price = prices
        return (input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price

    def complete(
        self,
        system: str,
        user: str,
        max_output_tokens: int = 4000,
        temperature: float = 0.2,
        timeout_s: int = 120,
    ) -> LLMResponse:
        """Make a single Anthropic Messages API call. Synchronous."""
        if self._is_killed():
            raise LLMUnavailable("llm_calls_killed switch is active")
        if not self.api_key:
            raise LLMUnavailable("ANTHROPIC_API_KEY not set in environment")

        # Lazy-import requests so this module compiles even on dev boxes
        # without the dep.
        import requests

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": max_output_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "temperature": temperature,
        }

        try:
            r = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
        except requests.exceptions.Timeout as e:
            raise LLMUnavailable(f"timeout: {e}") from e
        except requests.exceptions.RequestException as e:
            raise LLMUnavailable(f"request error: {e}") from e

        if r.status_code in (401, 403):
            raise LLMUnavailable(f"auth error: HTTP {r.status_code}")
        if r.status_code == 429:
            raise LLMUnavailable("rate-limited by Anthropic (HTTP 429)")
        if not r.ok:
            raise LLMUnavailable(f"HTTP {r.status_code}: {r.text[:300]}")

        try:
            body = r.json()
        except Exception as e:
            raise LLMUnavailable(f"non-JSON response: {e}") from e

        # Extract text from the messages-api response shape.
        content_blocks = body.get("content") or []
        text_chunks = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
        text = "\n".join(text_chunks).strip()

        usage = body.get("usage") or {}
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        usd = self._estimate_cost(input_tokens, output_tokens)

        # Meter the spend
        self._record("llm_tokens", float(input_tokens + output_tokens))
        self._record("llm_usd", float(usd))

        return LLMResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            usd_cost=usd,
            model=self.model,
            stop_reason=body.get("stop_reason"),
        )
