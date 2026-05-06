"""
Strategy interface for the backtester.

Every strategy implements:
    on_bar(bar, state) -> Signal | None
        Called per OHLC bar. May return a signal or None.

A Signal is one of: "long", "short", "exit". The backtester applies it to
the simulated portfolio.

State is a per-strategy dict the strategy maintains across calls
(rolling windows, indicators, etc.). The backtester passes the same dict
object back so the strategy doesn't need to hold instance state itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class Signal:
    direction: str          # "long", "short", or "exit"
    strength: float = 1.0   # for sizing; 1.0 = full size
    rationale: str = ""     # human-readable reason
    stop_distance: float | None = None
    target_distance: float | None = None


class Strategy(Protocol):
    name: str

    def on_bar(self, bar: Any, state: dict) -> Signal | None:
        ...


class StrategyBase:
    """Default base implementing common state helpers."""
    name: str = "base"

    def __init__(self, **kwargs: Any) -> None:
        self.params: dict = dict(kwargs)

    def on_bar(self, bar: Any, state: dict) -> Signal | None:
        raise NotImplementedError

    @staticmethod
    def push(state: dict, key: str, value: float, max_len: int) -> list[float]:
        """Append `value` to a rolling list at state[key], truncate to max_len."""
        lst = state.setdefault(key, [])
        lst.append(value)
        if len(lst) > max_len:
            del lst[: len(lst) - max_len]
        return lst
