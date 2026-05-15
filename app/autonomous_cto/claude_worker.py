from __future__ import annotations

from app.agent_ops.llm_client import LLMClient, LLMResponse, LLMUnavailable


def complete(
    prompt: str,
    system: str,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4000,
) -> dict:
    try:
        client = LLMClient(model=model)
        resp: LLMResponse = client.complete(
            system=system,
            user=prompt,
            max_output_tokens=max_tokens,
        )
        return {
            "ok": True,
            "text": resp.text,
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
            "cost_usd": resp.usd_cost,
            "model": resp.model,
        }
    except LLMUnavailable as e:
        return {"ok": False, "text": "", "error": str(e), "cost_usd": 0.0}
    except Exception as e:
        return {"ok": False, "text": "", "error": str(e), "cost_usd": 0.0}
