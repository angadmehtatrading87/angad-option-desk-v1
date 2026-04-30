from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class DeploymentDoctrine:
    target_pct: float
    floor_pct: float
    ceiling_pct: float
    mode: str
    should_expand: bool
    should_defend: bool
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def build_deployment_doctrine(
    regime: str,
    quality_score: float,
    current_deployment_pct: float,
    recent_drawdown_pct: float,
) -> DeploymentDoctrine:
    notes: list[str] = []

    if regime == "CHOP":
        floor, target, ceiling = 0.0, 5.0, 10.0
    elif regime == "MIXED":
        floor, target, ceiling = 10.0, 20.0, 30.0
    elif regime == "TREND_CONTINUATION":
        floor, target, ceiling = 25.0, 40.0, 55.0
    elif regime == "TREND_EXPANSION":
        floor, target, ceiling = 40.0, 60.0, 80.0
    else:
        floor, target, ceiling = 15.0, 25.0, 35.0

    if recent_drawdown_pct <= -0.5:
        notes.append("Recent drawdown present; reduce aggression.")
        target *= 0.7
        ceiling *= 0.8

    if quality_score < 50:
        notes.append("Regime quality weak; keep deployment light.")
        target *= 0.7

    should_expand = current_deployment_pct < floor
    should_defend = current_deployment_pct > ceiling

    mode = "DEFEND" if should_defend else "EXPAND" if should_expand else "MAINTAIN"
    return DeploymentDoctrine(round(target, 2), round(floor, 2), round(ceiling, 2), mode, should_expand, should_defend, notes)
