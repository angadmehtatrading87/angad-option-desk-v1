"""
Bollinger Band mean-reversion strategy.

Public-domain quant technique. Conceptually used by stat-arb desks (in
more sophisticated multi-asset variants).

Logic:
    Long  when close < lower band (price is N sigma below SMA)
    Short when close > upper band
    Exit  when close crosses back to SMA

Default 20-period SMA with 2-sigma bands (Bollinger's original parameters).
"""

from __future__ import annotations

import math

from app.research.strategy_base import StrategyBase, Signal


class BollingerMeanRevert(StrategyBase):
    name = "bollinger"

    def __init__(self, period: int = 20, sigma: float = 2.0) -> None:
        super().__init__(period=period, sigma=sigma)
        self.period = int(period)
        self.sigma = float(sigma)

    @staticmethod
    def _mean_std(values: list[float]) -> tuple[float, float]:
        n = len(values)
        if n == 0:
            return 0.0, 0.0
        mean = sum(values) / n
        var = sum((v - mean) ** 2 for v in values) / n
        return mean, math.sqrt(var)

    def on_bar(self, bar, state: dict) -> Signal | None:
        closes = self.push(state, "closes", float(bar.close), self.period)
        if len(closes) < self.period:
            return None

        mean, sd = self._mean_std(closes)
        upper = mean + self.sigma * sd
        lower = mean - self.sigma * sd
        close = float(bar.close)

        position = state.get("position", "flat")

        if position == "flat":
            if close < lower:
                state["position"] = "long"
                state["entry_price"] = close
                return Signal(direction="long", rationale=f"close {close:.5f} < lower band {lower:.5f} (mean {mean:.5f} - {self.sigma}σ)")
            if close > upper:
                state["position"] = "short"
                state["entry_price"] = close
                return Signal(direction="short", rationale=f"close {close:.5f} > upper band {upper:.5f}")
        elif position == "long":
            if close >= mean:
                state["position"] = "flat"
                return Signal(direction="exit", rationale=f"long mean-revert exit: close {close:.5f} >= mean {mean:.5f}")
        elif position == "short":
            if close <= mean:
                state["position"] = "flat"
                return Signal(direction="exit", rationale=f"short mean-revert exit: close {close:.5f} <= mean {mean:.5f}")

        return None
