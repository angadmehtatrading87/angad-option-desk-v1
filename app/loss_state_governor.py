from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class LossStateDirective:
    evidence_multiplier: float
    size_multiplier: float
    allow_pyramiding: bool
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def govern_after_losses(recent_realized_pnl: float, losing_streak: int) -> LossStateDirective:
    notes: list[str] = []
    evidence_multiplier = 1.0
    size_multiplier = 1.0
    allow_pyramiding = True

    if recent_realized_pnl < 0:
        evidence_multiplier *= 1.2
        size_multiplier *= 0.8
        notes.append("Recent realized losses; raise quality threshold.")

    if losing_streak >= 3:
        evidence_multiplier *= 1.25
        size_multiplier *= 0.75
        allow_pyramiding = False
        notes.append("Losing streak active; disable aggressive adding.")

    return LossStateDirective(round(evidence_multiplier, 2), round(size_multiplier, 2), allow_pyramiding, notes)
