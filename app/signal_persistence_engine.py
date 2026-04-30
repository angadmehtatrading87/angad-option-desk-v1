from __future__ import annotations

from collections import deque
from dataclasses import dataclass, asdict


@dataclass
class PersistenceState:
    symbol: str
    direction: str
    cycles_observed: int
    aligned_cycles: int
    persistence_score: float
    tradable: bool

    def to_dict(self) -> dict:
        return asdict(self)


class SignalPersistenceTracker:
    def __init__(self, maxlen: int = 12, min_aligned_cycles: int = 3) -> None:
        self.maxlen = maxlen
        self.min_aligned_cycles = min_aligned_cycles
        self._signals: dict[tuple[str, str], deque[int]] = {}

    def update(self, symbol: str, direction: str, aligned: bool) -> PersistenceState:
        key = (symbol, direction)
        buf = self._signals.setdefault(key, deque(maxlen=self.maxlen))
        buf.append(1 if aligned else 0)
        aligned_cycles = sum(buf)
        cycles = len(buf)
        score = round((aligned_cycles / max(cycles, 1)) * 100.0, 2)
        tradable = aligned_cycles >= self.min_aligned_cycles and score >= 60.0
        return PersistenceState(symbol, direction, cycles, aligned_cycles, score, tradable)
