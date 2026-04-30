from __future__ import annotations

from datetime import datetime, timezone


def build_trade_explanation(
    symbol: str,
    direction: str,
    regime: str,
    deployment_mode: str,
    score: float,
    reasons: list[str],
    size: float,
) -> dict:
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "direction": direction,
        "regime": regime,
        "deployment_mode": deployment_mode,
        "score": round(score, 2),
        "size": round(size, 4),
        "reasons": reasons,
    }
