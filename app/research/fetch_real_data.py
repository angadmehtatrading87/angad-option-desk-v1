"""
Fetch REAL historical FX data for the backtester (via yfinance).

Replaces the synthetic random-walk CSVs with actual market history, so the
backtest measures genuine edge instead of noise. yfinance is free, needs no API
key, and does NOT consume the IG price budget.

Run on the Lightsail box (it has the network access this needs):

    pip install yfinance --break-system-packages
    python -m app.research.fetch_real_data                 # 1H (~2y) + 1D (max), all 5 majors
    python -m app.research.fetch_real_data --interval 1h   # just hourly
    python -m app.research.fetch_real_data --symbol EURUSD  # single pair

Then re-run the comparison on the REAL data (no --synthetic flag):

    python -m app.research.run_full_comparison --save-json data/backtest_real_results.json

Output: data/historical/<SYMBOL>_<INTERVAL>.csv  with header
    timestamp,open,high,low,close,volume
Any existing CSV is backed up to <SYMBOL>_<INTERVAL>.synthetic.csv first (once),
so the old synthetic series is never lost.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import shutil
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HIST_DIR = os.path.join(BASE_DIR, "data", "historical")

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "USDCHF"]
YF_SYMBOL = {p: f"{p}=X" for p in PAIRS}

# our interval token -> yfinance params. yfinance caps intraday history:
# 1h is only available for ~730 days, so that's our hourly horizon.
INTERVAL_PLANS = {
    "1h": {"yf_interval": "1h", "period": "730d", "suffix": "1H"},
    "1d": {"yf_interval": "1d", "period": "max", "suffix": "1D"},
}

MIN_ROWS = 100  # refuse to overwrite good data with a near-empty fetch


def _out_path(symbol: str, suffix: str) -> str:
    return os.path.join(HIST_DIR, f"{symbol.upper()}_{suffix}.csv")


def _backup_existing(path: str) -> None:
    """Back up an existing CSV to <name>.synthetic.csv once, so we keep the
    original synthetic series for comparison and never destroy it silently."""
    if not os.path.exists(path):
        return
    backup = path[:-4] + ".synthetic.csv"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
        print(f"    backed up existing -> {os.path.basename(backup)}")


def _rows_from_df(df, yf_sym: str) -> list[list]:
    """Convert a yfinance OHLCV DataFrame into our CSV rows. Handles both flat
    and MultiIndex column layouts that different yfinance versions return."""
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df = df.copy()
        df.columns = df.columns.get_level_values(0)

    rows: list[list] = []
    for ts, r in df.iterrows():
        try:
            o = float(r["Open"]); h = float(r["High"])
            lo = float(r["Low"]); c = float(r["Close"])
        except Exception:
            continue
        if any(math.isnan(x) for x in (o, h, lo, c)):
            continue
        try:
            vol = float(r["Volume"])
            if math.isnan(vol):
                vol = 0.0
        except Exception:
            vol = 0.0
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        rows.append([ts_str, f"{o:.5f}", f"{h:.5f}", f"{lo:.5f}", f"{c:.5f}", f"{vol:.1f}"])
    return rows


def _write_csv(path: str, rows: list[list]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        w.writerows(rows)


def fetch_pair(symbol: str, plan: dict) -> int:
    """Fetch one pair/interval, write the CSV, return the row count written."""
    import yfinance as yf

    yf_sym = YF_SYMBOL.get(symbol.upper(), f"{symbol.upper()}=X")
    print(f"  {symbol} [{plan['suffix']}] downloading {yf_sym} "
          f"(interval={plan['yf_interval']}, period={plan['period']})...")
    try:
        df = yf.download(
            yf_sym,
            period=plan["period"],
            interval=plan["yf_interval"],
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception as e:
        print(f"    !! download failed: {e!r}")
        return 0

    if df is None or len(df) == 0:
        print("    !! no data returned (Yahoo may be rate-limiting; retry shortly)")
        return 0

    rows = _rows_from_df(df, yf_sym)
    if len(rows) < MIN_ROWS:
        print(f"    !! only {len(rows)} usable bars — refusing to overwrite. Keeping existing file.")
        return 0

    out = _out_path(symbol, plan["suffix"])
    _backup_existing(out)
    _write_csv(out, rows)
    print(f"    -> wrote {len(rows)} bars to {os.path.basename(out)} "
          f"({rows[0][0]} .. {rows[-1][0]})")
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch real FX history via yfinance")
    parser.add_argument("--symbol", default=None, help="Single symbol, or omit for all 5 majors")
    parser.add_argument("--interval", default="both", choices=["1h", "1d", "both"],
                        help="Which interval(s) to fetch (default: both)")
    args = parser.parse_args(argv)

    try:
        import yfinance  # noqa: F401
    except ImportError:
        print("yfinance is not installed. Install it first:\n"
              "    pip install yfinance --break-system-packages", file=sys.stderr)
        return 2

    os.makedirs(HIST_DIR, exist_ok=True)
    pairs = [args.symbol.upper()] if args.symbol else PAIRS
    intervals = ["1h", "1d"] if args.interval == "both" else [args.interval]

    print(f"\n=== fetching real FX data for {len(pairs)} pair(s), intervals={intervals} ===")
    total = 0
    for sym in pairs:
        for iv in intervals:
            total += fetch_pair(sym, INTERVAL_PLANS[iv])

    print(f"\nDone. {total} bars written across {len(pairs)} pair(s).")
    if total:
        print("Next: python -m app.research.run_full_comparison --save-json data/backtest_real_results.json")
    return 0 if total else 1


if __name__ == "__main__":
    sys.exit(main())
