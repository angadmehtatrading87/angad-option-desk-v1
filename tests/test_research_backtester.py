"""Smoke tests for the research/backtester module.

We synthesize a small in-memory price series and run each reference
strategy against it to confirm the contract holds end-to-end. No
historical CSV needed for these tests.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from app.research.data_loader import Bar
from app.research.strategies.donchian import DonchianBreakout
from app.research.strategies.bollinger import BollingerMeanRevert
from app.research.strategies.ma_crossover import MACrossover
from app.research.strategy_base import Signal


def _make_bars(prices: list[float]) -> list[Bar]:
    """Turn a list of close prices into Bars with synthetic OHLC."""
    bars = []
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for i, c in enumerate(prices):
        bars.append(Bar(
            ts=start + timedelta(hours=i),
            open=c, high=c * 1.0005, low=c * 0.9995, close=c,
            volume=0.0,
        ))
    return bars


def _run(strat, bars):
    state: dict = {}
    signals = []
    for b in bars:
        s = strat.on_bar(b, state)
        if s is not None:
            signals.append(s)
    return signals, state


def test_donchian_emits_long_on_breakout():
    # 30 bars of flat 1.10 then a clean break to 1.12 should fire a long
    prices = [1.10] * 25 + [1.12] * 5
    bars = _make_bars(prices)
    signals, _ = _run(DonchianBreakout(entry_window=20, exit_window=10), bars)
    assert any(s.direction == "long" for s in signals), (
        "Donchian should emit a long signal when close breaks above the prior 20-bar high"
    )


def test_donchian_no_signal_in_flat_market():
    bars = _make_bars([1.10] * 30)
    signals, _ = _run(DonchianBreakout(entry_window=20, exit_window=10), bars)
    assert not signals, "Donchian should be silent in a perfectly flat market"


def test_bollinger_emits_long_on_lower_band_break():
    # Build a series with a final extreme dip below the lower band
    prices = [1.10] * 30 + [1.08]  # 30 stable then an outlier
    bars = _make_bars(prices)
    signals, _ = _run(BollingerMeanRevert(period=20, sigma=2.0), bars)
    assert any(s.direction == "long" for s in signals)


def test_ma_crossover_signals_on_clean_uptrend():
    # First 200 bars sloping down, next 100 sloping up — clean golden cross
    prices = [1.10 - i * 0.0001 for i in range(200)] + [0.91 + i * 0.0005 for i in range(100)]
    bars = _make_bars(prices)
    signals, _ = _run(MACrossover(fast=50, slow=200), bars)
    long_count = sum(1 for s in signals if s.direction == "long")
    assert long_count >= 1, "MA crossover should fire at least one long signal on a golden cross"


def test_strategy_base_state_persists_across_calls():
    # Verify that DonchianBreakout actually uses state (not class instance vars)
    bars = _make_bars([1.10] * 25 + [1.12] * 5)
    strat = DonchianBreakout(entry_window=20, exit_window=10)
    state: dict = {}
    for b in bars:
        strat.on_bar(b, state)
    assert "highs" in state and len(state["highs"]) > 0


def test_strategy_signals_are_correctly_typed():
    bars = _make_bars([1.10] * 25 + [1.12] * 5)
    signals, _ = _run(DonchianBreakout(), bars)
    for s in signals:
        assert isinstance(s, Signal)
        assert s.direction in ("long", "short", "exit")
