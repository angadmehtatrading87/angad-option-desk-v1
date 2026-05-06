"""
Backtester CLI.

Examples:
    # Run one strategy on one pair
    python -m app.research.cli --symbol EURUSD --strategy donchian \\
        --start 2024-01-01 --end 2024-12-31

    # Compare all strategies on the same data
    python -m app.research.cli --symbol EURUSD --strategy all \\
        --start 2024-01-01 --end 2024-06-30

    # List what historical data is available
    python -m app.research.cli --list
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from app.research.backtester import run_backtest
from app.research.data_loader import list_available
from app.research.strategies import REGISTRY


def _parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a backtest against historical FX data.")
    parser.add_argument("--symbol", default="EURUSD",
                        help="FX symbol, e.g. EURUSD, USDCAD, USDJPY")
    parser.add_argument("--interval", default="1H",
                        help="Bar interval matching the CSV filename, default 1H")
    parser.add_argument("--strategy", default="donchian",
                        help=f"Strategy name (one of: {', '.join(REGISTRY.keys())}, or 'all')")
    parser.add_argument("--start", default=None, help="ISO date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="ISO date YYYY-MM-DD")
    parser.add_argument("--list", action="store_true",
                        help="List available historical CSVs and exit")
    parser.add_argument("--trades", action="store_true",
                        help="Print every closed trade as JSONL")
    args = parser.parse_args(argv)

    if args.list:
        avail = list_available()
        if not avail:
            print("No historical CSVs found at data/historical/. Run cleanup/download_fx_history.sh first.")
            return 1
        for sym, intv in avail:
            print(f"  {sym}_{intv}.csv")
        return 0

    start = _parse_date(args.start)
    end = _parse_date(args.end)

    if args.strategy == "all":
        strategies = list(REGISTRY.values())
    else:
        cls = REGISTRY.get(args.strategy)
        if not cls:
            print(f"Unknown strategy: {args.strategy}. Available: {list(REGISTRY.keys())}", file=sys.stderr)
            return 2
        strategies = [cls]

    rows = []
    for cls in strategies:
        strat = cls()
        result = run_backtest(strat, args.symbol, args.interval, start=start, end=end)
        rows.append(result)

    # Pretty-print summary table
    print(f"\nBacktest: {args.symbol} {args.interval}  ({start or 'beginning'} → {end or 'end'})")
    print("-" * 120)
    header = f"{'strategy':<14}{'bars':>8}{'trades':>8}{'final_pips':>12}{'max_dd':>10}{'win_rate':>10}{'avg_win':>10}{'avg_loss':>10}{'PF':>8}{'sharpe':>8}"
    print(header)
    print("-" * 120)
    for r in rows:
        s = r.to_summary()
        print(
            f"{s['strategy']:<14}{s['bars']:>8}{s['trades']:>8}{s['final_pips']:>12}"
            f"{s['max_drawdown_pips']:>10}{s['win_rate_pct']:>10}{s['avg_win_pips']:>10}"
            f"{s['avg_loss_pips']:>10}{s['profit_factor']:>8}{s['sharpe']:>8}"
        )
    print("-" * 120)

    if args.trades and rows:
        print("\nClosed trades:")
        for r in rows:
            for t in r.trades:
                print(json.dumps({
                    "strategy": r.strategy_name,
                    "entry_ts": t.entry_ts.isoformat(),
                    "exit_ts": t.exit_ts.isoformat() if t.exit_ts else None,
                    "direction": t.direction,
                    "entry": t.entry_price,
                    "exit": t.exit_price,
                    "pnl_pips": t.pnl_pips,
                    "in": t.rationale_in,
                    "out": t.rationale_out,
                }, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
