from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class PairEdgeProfile:
    symbol: str
    expectancy: float
    win_rate: float
    avg_hold_minutes: float
    preferred_sessions: list[str]
    size_weight: float
    enabled: bool
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def build_pair_edge_profile(
    symbol: str,
    expectancy: float,
    win_rate: float,
    avg_hold_minutes: float,
    preferred_sessions: list[str],
) -> PairEdgeProfile:
    notes: list[str] = []
    enabled = True
    size_weight = 1.0

    if expectancy < 0 or win_rate < 40:
        enabled = False
        size_weight = 0.0
        notes.append("Negative or weak edge; disable or quarantine pair.")
    elif expectancy < 5:
        size_weight = 0.6
        notes.append("Thin edge; downweight pair.")
    elif expectancy > 20 and win_rate > 50:
        size_weight = 1.4
        notes.append("Strong edge; overweight pair.")

    return PairEdgeProfile(symbol, expectancy, win_rate, avg_hold_minutes, preferred_sessions, size_weight, enabled, notes)
