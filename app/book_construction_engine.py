from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class BookDirective:
    target_position_count: int
    target_deployment_pct: float
    max_single_pair_pct: float
    max_synthetic_usd_pct: float
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def construct_book_directive(
    target_deployment_pct: float,
    quality_score: float,
) -> BookDirective:
    if target_deployment_pct <= 10:
        count = 1
    elif target_deployment_pct <= 25:
        count = 2
    elif target_deployment_pct <= 40:
        count = 3
    elif target_deployment_pct <= 60:
        count = 4
    else:
        count = 5

    max_single_pair_pct = 18.0 if quality_score >= 70 else 12.0
    max_synthetic_usd_pct = 55.0 if quality_score >= 70 else 40.0

    return BookDirective(count, target_deployment_pct, max_single_pair_pct, max_synthetic_usd_pct, ["Prefer fewer, larger expressions."])
