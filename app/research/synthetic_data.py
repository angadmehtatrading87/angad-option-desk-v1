"""
Synthetic 10-year FX OHLC generator.

Used when real HistData CSVs aren't available. Produces 1-hour bars with
realistic FX behavior: drift, vol clustering (GARCH-like), regime shifts,
and pair-specific volatility profiles.

NOT a substitute for real HistData — but for sanity-checking strategy
relative performance, it's good enough. A strategy that looks good here
should also look good on real data; one that bleeds here will likely bleed
on real data too.

Usage:
    from app.research.synthetic_data import generate_synthetic_csv
    generate_synthetic_csv("EURUSD", years=10, out_path="data/historical/EURUSD_1H.csv")
"""

from __future__ import annotations

import csv
import math
import os
import random
from datetime import datetime, timedelta, timezone

# Per-pair parameters tuned to roughly match real FX behavior over the
# 2014-2024 era. These are coarse — drift % per year, base hourly vol,
# typical pair price level.
PAIR_PARAMS = {
    "EURUSD": {"start_price": 1.20,  "annual_drift": -0.015, "base_vol_pct": 0.0007},
    "GBPUSD": {"start_price": 1.55,  "annual_drift": -0.025, "base_vol_pct": 0.0009},
    "USDJPY": {"start_price": 105.0, "annual_drift":  0.020, "base_vol_pct": 0.0007},
    "USDCAD": {"start_price": 1.10,  "annual_drift":  0.005, "base_vol_pct": 0.0006},
    "USDCHF": {"start_price": 0.95,  "annual_drift":  0.005, "base_vol_pct": 0.0006},
}

BARS_PER_YEAR = 24 * 252  # ~6048 trading hours/year


def _generate_returns(n_bars: int, base_vol: float, seed: int) -> list[float]:
    """GARCH-flavored hourly returns: vol clusters, occasional regime shifts."""
    rng = random.Random(seed)
    returns = []
    current_vol = base_vol
    regime = 1.0  # multiplier on vol; switches between calm (0.6), normal (1.0), stressed (1.8)

    for i in range(n_bars):
        # Occasional regime shifts (~once every 600 bars = ~once a month)
        if rng.random() < 1.0 / 600.0:
            regime = rng.choice([0.6, 1.0, 1.0, 1.0, 1.8])  # bias toward normal

        # Volatility clusters — vol slowly mean-reverts to base
        target_vol = base_vol * regime
        current_vol += (target_vol - current_vol) * 0.05
        # Add occasional vol shocks
        if rng.random() < 1.0 / 300.0:
            current_vol *= rng.uniform(1.5, 3.0)

        # Hourly return: gaussian * current vol
        r = rng.gauss(0, current_vol)
        returns.append(r)

    return returns


def _generate_ohlc_series(
    start_price: float,
    n_bars: int,
    annual_drift: float,
    base_vol: float,
    seed: int,
    start_dt: datetime,
) -> list[tuple]:
    """Returns list of (ts, open, high, low, close, volume)."""
    hourly_drift = annual_drift / BARS_PER_YEAR
    returns = _generate_returns(n_bars, base_vol, seed)

    # Sub-bar noise for realistic high/low: each hour bar gets ~5 sub-ticks
    rng = random.Random(seed + 1)

    bars = []
    price = start_price
    for i, r in enumerate(returns):
        ts = start_dt + timedelta(hours=i)
        # Skip weekends (FX market closed Sat 22:00 → Sun 22:00 UTC roughly)
        weekday = ts.weekday()  # 0=Mon, 6=Sun
        if weekday == 5:  # Saturday
            continue
        if weekday == 6 and ts.hour < 22:  # Sunday before reopen
            continue

        bar_open = price
        bar_close = price * (1.0 + r + hourly_drift)
        # Generate 5 intra-bar sub-ticks for realistic high/low
        sub_high = max(bar_open, bar_close)
        sub_low = min(bar_open, bar_close)
        for _ in range(5):
            wiggle = rng.gauss(0, base_vol * 0.5)
            mid = (bar_open + bar_close) / 2 * (1.0 + wiggle)
            sub_high = max(sub_high, mid)
            sub_low = min(sub_low, mid)
        bars.append((
            ts.strftime("%Y-%m-%d %H:%M:%S"),
            round(bar_open, 5),
            round(sub_high, 5),
            round(sub_low, 5),
            round(bar_close, 5),
            0.0,
        ))
        price = bar_close

    return bars


def generate_synthetic_csv(
    symbol: str,
    years: int = 10,
    out_path: str | None = None,
    seed: int | None = None,
) -> str:
    """Write a synthetic CSV in the format the data_loader expects.

    Returns the output path."""
    params = PAIR_PARAMS.get(symbol.upper())
    if not params:
        raise ValueError(f"Unknown symbol {symbol}; supported: {list(PAIR_PARAMS)}")

    n_bars = years * BARS_PER_YEAR
    end = datetime(2024, 12, 31, 22, 0, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=n_bars)
    seed = seed if seed is not None else (hash(symbol.upper()) & 0x7FFFFFFF)

    bars = _generate_ohlc_series(
        start_price=params["start_price"],
        n_bars=n_bars,
        annual_drift=params["annual_drift"],
        base_vol=params["base_vol_pct"],
        seed=seed,
        start_dt=start,
    )

    if out_path is None:
        out_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data", "historical", f"{symbol.upper()}_1H.csv",
        )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for row in bars:
            w.writerow(row)

    return out_path


if __name__ == "__main__":
    import sys
    syms = sys.argv[1:] or list(PAIR_PARAMS.keys())
    for s in syms:
        path = generate_synthetic_csv(s, years=10)
        print(f"wrote {path}")
