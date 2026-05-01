from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Literal

Direction = Literal['long','short','flat']
Action = Literal['trade','watch','reject']

@dataclass
class CandleFeatures:
    epic: str
    available: bool
    trend_5m: float
    trend_1h: float
    trend_4h: float
    momentum: float
    body_quality: float
    wick_imbalance: float
    breakout_strength: float
    breakdown_strength: float
    gap_score: float
    sr_proximity: float
    vol_compression: float
    vol_expansion: float
    mean_reversion_signal: float
    continuation_signal: float
    failed_breakout_risk: float

@dataclass
class MarketScanResult:
    epic: str
    spread_bps: float
    friction_score: float
    liquidity_score: float
    mover_score: float
    quiet_market: bool
    trend_cleanliness: float

@dataclass
class RegimeSignal:
    label: str
    confidence: float
    no_trade: bool
    rationale: str

@dataclass
class NewsSignal:
    source_connected: bool
    risk_sentiment: str
    confidence: float | None
    headline_count: int
    note: str

@dataclass
class OpportunityScore:
    epic: str
    direction: Direction
    opportunity_score: float
    confidence_score: float
    expected_edge: float
    expected_risk: float
    expected_reward: float
    rr_ratio: float
    friction_cost_estimate: float
    action: Action
    rejection_reason: str | None = None
    components: dict[str, float] = field(default_factory=dict)

@dataclass
class TradeThesis:
    epic: str
    direction: Direction
    why_instrument: str
    why_direction: str
    why_now: str
    structure: str
    regime: str
    invalidation: str
    expected_move: str
    stop_logic: str
    take_profit_logic: str
    rr_summary: str
    recommended_size: float
    confidence: float
    deployment_stance: str

@dataclass
class CapitalAllocationRecommendation:
    total_capital: float
    min_reserve: float
    committed_exposure: float
    deployable_capital: float
    current_used_capital: float
    unused_capital: float
    monthly_on_track: bool
    target_return_low: float
    target_return_high: float
    recommendation_note: str

@dataclass
class MonthlyObjectiveState:
    month_start_capital: float
    current_capital: float
    monthly_realized_pnl: float
    monthly_unrealized_pnl: float
    monthly_return_pct: float
    target_low_pct: float = 4.0
    target_high_pct: float = 5.0
    required_remaining_pct: float = 0.0
    trading_days_remaining: int = 0
    status: str = 'on_track'

@dataclass
class LearningFeedbackRecord:
    epic: str
    setup_type: str
    regime: str
    confidence: float
    thesis_quality: float
    outcome: str
    reason: str

@dataclass
class MarketBrainInput:
    watchlist: list[dict[str, Any]]
    candles: dict[str, list[dict[str, Any]]]
    account: dict[str, Any]
    positions: list[dict[str, Any]]
    monthly: dict[str, Any]

@dataclass
class MarketBrainOutput:
    generated_at: str
    regime: RegimeSignal
    news: NewsSignal
    monthly: MonthlyObjectiveState
    capital: CapitalAllocationRecommendation
    opportunities: list[OpportunityScore]
    thesis: list[TradeThesis]
    rejected: list[OpportunityScore]
    diagnostics: dict[str, Any]

    def to_dict(self):
        return asdict(self)
