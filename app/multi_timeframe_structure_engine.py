from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class StructureView:
    bias: str
    strength: float
    continuation_probability: float
    invalidation_level: float | None
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def infer_structure_view(
    tf_data: dict[str, dict],
) -> StructureView:
    """
    tf_data example:
    {
      "5m": {"trend": 1, "slope": 0.3, "hhhl": True, "breakout": False, "last_price": 1.0765, "support": 1.0740, "resistance": 1.0780},
      "1h": {...}
    }
    """
    score = 0.0
    notes: list[str] = []
    long_votes = 0
    short_votes = 0
    invalidation = None

    for tf, row in tf_data.items():
        trend = int(row.get("trend", 0))
        slope = float(row.get("slope", 0.0))
        if trend > 0:
            long_votes += 1
            score += slope
        elif trend < 0:
            short_votes += 1
            score -= abs(slope)

        if row.get("hhhl"):
            notes.append(f"{tf} higher-high / higher-low structure.")
        if row.get("lllh"):
            notes.append(f"{tf} lower-low / lower-high structure.")

    if long_votes > short_votes:
        bias = "LONG"
        strength = min(abs(score) * 100, 100.0)
    elif short_votes > long_votes:
        bias = "SHORT"
        strength = min(abs(score) * 100, 100.0)
    else:
        bias = "NEUTRAL"
        strength = 20.0

    continuation_probability = min(95.0, max(5.0, 50.0 + (strength - 50.0) * 0.6))

    if bias == "LONG":
        invalidation = min((row.get("support") for row in tf_data.values() if row.get("support") is not None), default=None)
    elif bias == "SHORT":
        invalidation = max((row.get("resistance") for row in tf_data.values() if row.get("resistance") is not None), default=None)

    return StructureView(bias, round(strength, 2), round(continuation_probability, 2), invalidation, notes)
