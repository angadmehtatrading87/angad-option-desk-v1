"""
market_brain wrapped as a backtester strategy.

Uses the same `score_candidate` and `detect_regime` functions from
`autonomous_trader_architecture` that the live trader runs through, so the
backtest result is a direct read on whether the live bot's decision math
has edge.

Caveats / approximations:
    - Live `build_agent_v2_plan` has multi-timeframe + structure +
      persistence layers that this strategy does NOT have (we only run on
      a single TF here). Treat the result as a lower bound — the live
      bot, with MTF agreement filtering, should perform at LEAST as well.
    - Live sizing uses regime-aware capital allocation; here we use flat
      1-lot. P&L numbers are pip-based, comparable across strategies.
    - Stop-loss / take-profit logic isn't applied; entries persist until
      score drops below an exit threshold (mirrors the live exit doctrine
      at a basic level).
"""

from __future__ import annotations

from app.research.strategy_base import StrategyBase, Signal


def _ema(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    k = 2.0 / (period + 1)
    e = float(values[0])
    for v in values[1:]:
        e = float(v) * k + e * (1 - k)
    return e


def _slope_pct(closes: list[float], lookback: int = 10) -> float:
    if len(closes) <= lookback:
        return 0.0
    base = closes[-1 - lookback]
    if base == 0:
        return 0.0
    return ((closes[-1] - base) / base) * 100.0


def _spread_bps(bar) -> float:
    """We don't have bid/ask in our backtest bars; assume a typical FX
    1-pip spread (~1 bp on majors). Live uses real bid/ask."""
    return 1.0


class MarketBrainStrategy(StrategyBase):
    name = "market_brain"

    def __init__(
        self,
        score_threshold: float = 65.0,
        exit_score_floor: float = 50.0,
        regime_min_confidence: float = 50.0,
    ) -> None:
        super().__init__(
            score_threshold=score_threshold,
            exit_score_floor=exit_score_floor,
            regime_min_confidence=regime_min_confidence,
        )
        self.score_threshold = float(score_threshold)
        self.exit_score_floor = float(exit_score_floor)
        self.regime_min_confidence = float(regime_min_confidence)

    def on_bar(self, bar, state: dict) -> Signal | None:
        # Push bar onto rolling candle window
        bar_dict = {
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
        }
        candles = state.setdefault("candles", [])
        candles.append(bar_dict)
        # Keep last 60 bars for regime + indicators
        if len(candles) > 60:
            del candles[: len(candles) - 60]

        # Need enough history for regime classifier
        if len(candles) < 25:
            return None

        # Lazy-import the live scoring engine so this module compiles even if
        # autonomous_trader_architecture's deps aren't loaded.
        from app.autonomous_trader_architecture import (
            detect_regime, score_candidate, Candidate,
        )

        # Build features the same way the live engine does
        closes = [c["close"] for c in candles]
        ema_fast = _ema(closes[-30:], 9)
        ema_slow = _ema(closes[-30:], 21)
        slope = _slope_pct(closes)

        # Trend score: EMA spread normalized to a 0-100 band
        if ema_fast > ema_slow * 1.0001:
            trend_score = min(100.0, 50.0 + (ema_fast - ema_slow) / ema_slow * 5000.0)
            direction_hint = "long"
        elif ema_fast < ema_slow * 0.9999:
            trend_score = min(100.0, 50.0 + (ema_slow - ema_fast) / ema_slow * 5000.0)
            direction_hint = "short"
        else:
            trend_score = 50.0
            direction_hint = "flat"

        # Momentum: abs slope mapped to 0-100
        momentum_score = max(0.0, min(100.0, 50.0 + abs(slope) * 8.0))

        # Structure: simple breakout vs swing highs/lows
        recent_window = candles[-20:]
        prior_window = candles[-40:-20] if len(candles) >= 40 else recent_window
        prior_high = max((c["high"] for c in prior_window), default=closes[-1])
        prior_low = min((c["low"] for c in prior_window), default=closes[-1])
        last_close = closes[-1]
        if last_close > prior_high:
            structure_score = 75.0
        elif last_close < prior_low:
            structure_score = 75.0
        else:
            structure_score = 45.0

        # Volatility: ATR-derived score (high vol = more conviction)
        trs = []
        for i in range(max(1, len(candles) - 14), len(candles)):
            c = candles[i]
            p = candles[i - 1]
            tr = max(c["high"] - c["low"], abs(c["high"] - p["close"]), abs(c["low"] - p["close"]))
            trs.append(tr)
        atr = sum(trs) / len(trs) if trs else 0.0
        atr_pct = (atr / last_close) if last_close else 0.0
        volatility_score = max(20.0, min(100.0, 50.0 + atr_pct * 20000.0))

        # R:R: assume 1.5:1 if trending, 1.0:1 if not (proxy)
        rr = 1.6 if direction_hint != "flat" else 1.0

        # Regime classification
        regime = detect_regime(candles)
        regime_conf = float(regime.get("confidence") or 0.0)

        # Build the candidate object for scoring
        candidate = Candidate(
            epic=getattr(bar, "epic", "X"),
            direction=direction_hint if direction_hint != "flat" else "long",
            spread_bps=_spread_bps(bar),
            momentum=momentum_score,
            trend=trend_score,
            structure=structure_score,
            volatility=volatility_score,
            rr=rr,
            confidence=70.0 if direction_hint != "flat" else 40.0,
        )
        result = score_candidate(candidate, regime)
        score = float(result.get("tradability_score") or 0.0)

        # Track score history for diagnostics
        state.setdefault("score_history", []).append(score)
        if len(state["score_history"]) > 200:
            del state["score_history"][:100]

        position = state.get("position", "flat")

        # Entry: score above threshold AND regime is tradable
        if position == "flat":
            if (
                score >= self.score_threshold
                and direction_hint != "flat"
                and regime.get("regime") not in ("NO_TRADE", "CHOP")
                and regime_conf >= self.regime_min_confidence
            ):
                state["position"] = direction_hint
                state["entry_score"] = score
                state["entry_price"] = last_close
                return Signal(
                    direction=direction_hint,
                    rationale=(
                        f"market_brain entry: score={score:.1f} "
                        f"regime={regime.get('regime')} ({regime_conf:.0f}) "
                        f"trend={trend_score:.0f} mom={momentum_score:.0f}"
                    ),
                )
        else:
            # Exit: score collapsed OR direction flipped OR regime turned NO_TRADE
            should_exit = (
                score < self.exit_score_floor
                or regime.get("regime") == "NO_TRADE"
                or (direction_hint != "flat" and direction_hint != position)
            )
            if should_exit:
                state["position"] = "flat"
                return Signal(
                    direction="exit",
                    rationale=(
                        f"market_brain exit: score dropped {state.get('entry_score', 0):.0f}->{score:.0f} "
                        f"regime={regime.get('regime')} dir_now={direction_hint}"
                    ),
                )

        return None
