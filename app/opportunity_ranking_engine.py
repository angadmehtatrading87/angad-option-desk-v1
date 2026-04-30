from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class OpportunityScore:
    symbol: str
    direction: str
    total_score: float
    reasons: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def rank_opportunity(
    symbol: str,
    direction: str,
    structure_strength: float,
    persistence_score: float,
    regime_quality: float,
    friction_penalty: float,
    pair_size_weight: float,
    portfolio_fit: float,
) -> OpportunityScore:
    score = (
        structure_strength * 0.28
        + persistence_score * 0.22
        + regime_quality * 0.18
        + portfolio_fit * 0.17
        + pair_size_weight * 25.0
        - friction_penalty * 0.15
    )
    reasons = [
        f"structure={structure_strength:.1f}",
        f"persistence={persistence_score:.1f}",
        f"regime_quality={regime_quality:.1f}",
        f"portfolio_fit={portfolio_fit:.1f}",
        f"pair_weight={pair_size_weight:.2f}",
        f"friction_penalty={friction_penalty:.1f}",
    ]
    return OpportunityScore(symbol, direction, round(score, 2), reasons)
