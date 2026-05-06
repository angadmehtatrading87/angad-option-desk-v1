"""
Moving Average crossover strategy.

Textbook trend-following — variants used across CTA funds (AHL, Winton,
Campbell). The simplest signal in trend literature.

Logic:
    Long  when fast SMA crosses above slow SMA
    Short when fast SMA crosses below slow SMA
    Exit  when the next opposite cross occurs (always-in-market variant)

Default 50/200 (the famous "death cross / golden cross" used on daily
charts). On 1H bars 50/200 corresponds to ~2 days vs ~8 days, which is a
medium-term swing setting.
"""

from __future__ import annotations

from app.research.strategy_base import StrategyBase, Signal


class MACrossover(StrategyBase):
    name = "ma_crossover"

    def __init__(self, fast: int = 50, slow: int = 200) -> None:
        super().__init__(fast=fast, slow=slow)
        if fast >= slow:
            raise ValueError("fast period must be < slow period")
        self.fast = int(fast)
        self.slow = int(slow)

    @staticmethod
    def _sma(values: list[float], n: int) -> float | None:
        if len(values) < n:
            return None
        return sum(values[-n:]) / n

    def on_bar(self, bar, state: dict) -> Signal | None:
        closes = self.push(state, "closes", float(bar.close), self.slow + 5)
        if len(closes) < self.slow:
            return None

        fast_now = self._sma(closes, self.fast)
        slow_now = self._sma(closes, self.slow)
        if fast_now is None or slow_now is None:
            return None

        # Previous SMAs from one bar ago
        if len(closes) < self.slow + 1:
            state["last_diff_sign"] = (1 if fast_now > slow_now else -1)
            return None
        prev_closes = closes[:-1]
        fast_prev = self._sma(prev_closes, self.fast)
        slow_prev = self._sma(prev_closes, self.slow)

        diff_now = fast_now - slow_now
        diff_prev = fast_prev - slow_prev

        position = state.get("position", "flat")
        close = float(bar.close)

        # Detect a sign-change in the SMA spread (the actual crossover)
        crossed_up = diff_prev <= 0 < diff_now
        crossed_down = diff_prev >= 0 > diff_now

        if crossed_up:
            if position != "long":
                exit_first = position == "short"
                state["position"] = "long"
                state["entry_price"] = close
                rationale = f"fast SMA{self.fast} {fast_now:.5f} crossed above slow SMA{self.slow} {slow_now:.5f}"
                if exit_first:
                    # Always-in-market: emit exit + new entry. Backtester
                    # treats this as a single direction-flip.
                    return Signal(direction="long", rationale=f"flip from short — {rationale}")
                return Signal(direction="long", rationale=rationale)
        elif crossed_down:
            if position != "short":
                state["position"] = "short"
                state["entry_price"] = close
                rationale = f"fast SMA{self.fast} {fast_now:.5f} crossed below slow SMA{self.slow} {slow_now:.5f}"
                return Signal(direction="short", rationale=rationale)

        return None
