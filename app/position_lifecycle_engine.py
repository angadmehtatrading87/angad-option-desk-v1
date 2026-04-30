from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class PositionLifecycle:
    state: str
    should_add: bool
    should_hold: bool
    should_harvest: bool
    should_exit: bool
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def assess_position_lifecycle(
    pnl_points: float,
    structure_aligned: bool,
    persistence_score: float,
    age_minutes: float,
) -> PositionLifecycle:
    notes: list[str] = []

    if not structure_aligned and pnl_points < 0:
        return PositionLifecycle("EXIT", False, False, False, True, ["Structure broken and trade losing."])

    if pnl_points > 0 and persistence_score >= 70 and age_minutes >= 30:
        notes.append("Strong runner status.")
        return PositionLifecycle("RUNNER", False, True, False, False, notes)

    if pnl_points > 0 and persistence_score < 55:
        notes.append("Winner fading; harvest candidate.")
        return PositionLifecycle("HARVEST", False, False, True, False, notes)

    if pnl_points <= 0 and structure_aligned:
        notes.append("Valid thesis but not working yet.")
        return PositionLifecycle("ACTIVE", False, True, False, False, notes)

    return PositionLifecycle("BUILD", True, True, False, False, ["Eligible for controlled add."])
