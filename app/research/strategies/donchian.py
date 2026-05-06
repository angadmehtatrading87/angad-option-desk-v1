"""
Donchian channel breakout strategy.

Public-domain trend-following technique — basis of the famous "Turtle
Traders" system, also widely used by CTA funds like AHL, Winton, Man.

Logic:
    Long  when close > high of last `entry_window` bars
    Short when close < low  of last `entry_window` bars
    Exit  when close crosses opposite extreme of `exit_window` bars

Default 20/10 (20-bar entry, 10-bar exit) is conservative; 55/20 is the
classic Turtle "System 2"; we use 20/10 because it generates more trades
on FX 1H bars (better for backtesting feedback).
"""

from __future__ import annotations

from app.research.strategy_base import StrategyBase, Signal


class DonchianBreakout(StrategyBase):
    name = "donchian"

    def __init__(self, entry_window: int = 20, exit_window: int = 10) -> None:
        super().__init__(entry_window=entry_window, exit_window=exit_window)
        self.entry_window = int(entry_window)
        self.exit_window = int(exit_window)

    def on_bar(self, bar, state: dict) -> Signal | None:
        highs = self.push(state, "highs", float(bar.high), self.entry_window + 1)
        lows = self.push(state, "lows", float(bar.low), self.entry_window + 1)

        if len(highs) <= self.entry_window:
            # Not enough history yet
            return None

        prev_highs = highs[:-1]   # exclude current bar
        prev_lows = lows[:-1]
        entry_high = max(prev_highs[-self.entry_window:])
        entry_low = min(prev_lows[-self.entry_window:])
        exit_high = max(prev_highs[-self.exit_window:])
        exit_low = min(prev_lows[-self.exit_window:])

        position = state.get("position", "flat")
        close = float(bar.close)

        if position == "flat":
            if close > entry_high:
                state["position"] = "long"
                state["entry_price"] = close
                return Signal(direction="long", rationale=f"close {close:.5f} > donchian {self.entry_window}h high {entry_high:.5f}")
            if close < entry_low:
                state["position"] = "short"
                state["entry_price"] = close
                return Signal(direction="short", rationale=f"close {close:.5f} < donchian {self.entry_window}l low {entry_low:.5f}")
        elif position == "long":
            if close < exit_low:
                state["position"] = "flat"
                return Signal(direction="exit", rationale=f"long exit: close {close:.5f} < {self.exit_window}-bar low {exit_low:.5f}")
        elif position == "short":
            if close > exit_high:
                state["position"] = "flat"
                return Signal(direction="exit", rationale=f"short exit: close {close:.5f} > {self.exit_window}-bar high {exit_high:.5f}")

        return None
