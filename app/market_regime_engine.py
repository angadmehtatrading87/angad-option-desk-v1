from __future__ import annotations

from dataclasses import dataclass, asdict
from statistics import mean


@dataclass
class RegimeDecision:
    regime: str
    quality_score: float
    deployment_band_pct: tuple[float, float]
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def classify_market_regime(
    mtf_slopes: dict[str, float],
    realized_vol: float,
    range_expansion: float,
    session: str,
    persistence_score: float,
) -> RegimeDecision:
    notes: list[str] = []
    avg_slope = mean(mtf_slopes.values()) if mtf_slopes else 0.0
    slope_abs = abs(avg_slope)

    if realized_vol < 0.15 and range_expansion < 0.2:
        notes.append("Low volatility / weak expansion.")
        return RegimeDecision("CHOP", 25.0, (0.0, 10.0), notes)

    if persistence_score > 70 and slope_abs > 0.35 and range_expansion > 0.6:
        notes.append("Persistent directional move with expansion.")
        return RegimeDecision("TREND_EXPANSION", 85.0, (40.0, 70.0), notes)

    if persistence_score > 55 and slope_abs > 0.2:
        notes.append("Trend continuation conditions.")
        return RegimeDecision("TREND_CONTINUATION", 70.0, (25.0, 50.0), notes)

    if realized_vol > 0.8 and range_expansion > 1.2:
        notes.append("Breakout or post-news instability.")
        return RegimeDecision("BREAKOUT_HIGH_VOL", 60.0, (15.0, 35.0), notes)

    notes.append("Mixed conditions.")
    return RegimeDecision("MIXED", 45.0, (10.0, 25.0), notes)
