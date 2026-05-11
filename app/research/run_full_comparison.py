"""
Run all strategies against all 5 FX majors and produce a comparison report.

Usage:
    # Sanity-check with synthetic 10-year data (auto-generated):
    python -m app.research.run_full_comparison --synthetic

    # Real data (HistData CSVs already in data/historical/):
    python -m app.research.run_full_comparison

    # Single symbol:
    python -m app.research.run_full_comparison --symbol EURUSD --synthetic

Output: a comparison table with one row per (symbol, strategy) showing:
    bars · trades · final_pips · max_drawdown · win_rate · profit_factor · sharpe
And a summary verdict at the bottom.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

from app.research.backtester import run_backtest
from app.research.data_loader import historical_path, list_available
from app.research.strategies import REGISTRY


PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "USDCHF"]


def ensure_synthetic(pairs: list[str], years: int = 10) -> None:
    from app.research.synthetic_data import generate_synthetic_csv
    for p in pairs:
        path = historical_path(p, "1H")
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            print(f"  {p}: already present at {path} (skipping)")
            continue
        print(f"  {p}: generating {years}-year synthetic series...")
        generate_synthetic_csv(p, years=years)
        print(f"    -> wrote {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default=None, help="Single symbol or omit for all 5 majors")
    parser.add_argument("--synthetic", action="store_true",
                        help="Generate synthetic 10-year data if real CSV missing")
    parser.add_argument("--years", type=int, default=10)
    parser.add_argument("--strategy", default="all",
                        help="Single strategy or 'all'")
    parser.add_argument("--save-json", default=None, help="Optional path to save full results")
    args = parser.parse_args(argv)

    pairs = [args.symbol] if args.symbol else PAIRS

    if args.synthetic:
        print(f"\n=== ensuring {args.years}y synthetic data for {len(pairs)} pairs ===")
        ensure_synthetic(pairs, years=args.years)

    if args.strategy == "all":
        strategies = list(REGISTRY.values())
    else:
        cls = REGISTRY.get(args.strategy)
        if not cls:
            print(f"unknown strategy: {args.strategy}", file=sys.stderr)
            return 2
        strategies = [cls]

    available = dict(list_available())  # {(symbol, interval): None} → flattened later
    available_set = set(available.keys()) if isinstance(available, dict) else set()
    # list_available actually returns a list of tuples; recompute
    available_set = set(list_available())

    results = []
    for sym in pairs:
        if (sym, "1H") not in available_set:
            print(f"\n!! No historical CSV for {sym}_1H. Run with --synthetic or download HistData.")
            continue

        for cls in strategies:
            strat = cls()
            res = run_backtest(strat, sym, "1H")
            results.append(res)

    # Print comparison table
    print("\n" + "=" * 130)
    header = f"{'symbol':<8} {'strategy':<15} {'bars':>8} {'trades':>8} {'final_pips':>12} {'max_dd':>10} {'win%':>8} {'avg_win':>10} {'avg_loss':>10} {'PF':>7} {'sharpe':>8}"
    print(header)
    print("=" * 130)
    for r in results:
        s = r.to_summary()
        print(
            f"{s['symbol']:<8} {s['strategy']:<15} {s['bars']:>8} {s['trades']:>8} "
            f"{s['final_pips']:>12} {s['max_drawdown_pips']:>10} {s['win_rate_pct']:>8} "
            f"{s['avg_win_pips']:>10} {s['avg_loss_pips']:>10} {s['profit_factor']:>7} {s['sharpe']:>8}"
        )
    print("=" * 130)

    # Aggregate by strategy across all pairs
    by_strat: dict[str, dict] = {}
    for r in results:
        agg = by_strat.setdefault(r.strategy_name, {
            "trades": 0, "final_pips": 0.0, "wins": 0, "loss_count": 0, "sharpes": [],
        })
        closed = [t for t in r.trades if t.pnl_pips is not None]
        agg["trades"] += len(closed)
        agg["final_pips"] += r.final_equity_pips
        agg["wins"] += sum(1 for t in closed if (t.pnl_pips or 0) > 0)
        agg["loss_count"] += sum(1 for t in closed if (t.pnl_pips or 0) <= 0)
        if r.sharpe:
            agg["sharpes"].append(r.sharpe)

    print("\n=== STRATEGY VERDICT (aggregated across all pairs) ===")
    print(f"{'strategy':<15} {'total_trades':>14} {'total_pips':>12} {'win%':>8} {'avg_sharpe':>12}")
    print("-" * 70)
    rows = []
    for name, agg in by_strat.items():
        total = agg["trades"]
        wp = (agg["wins"] / total * 100.0) if total else 0.0
        avg_sharpe = sum(agg["sharpes"]) / len(agg["sharpes"]) if agg["sharpes"] else 0.0
        rows.append((name, total, agg["final_pips"], wp, avg_sharpe))

    # Sort by total pips desc
    rows.sort(key=lambda x: x[2], reverse=True)
    for name, total, pips, wp, sh in rows:
        print(f"{name:<15} {total:>14} {pips:>12.1f} {wp:>7.1f}% {sh:>12.3f}")
    print("-" * 70)

    if rows:
        winner = rows[0]
        mb_row = next((r for r in rows if r[0] == "market_brain"), None)
        print(f"\nBest strategy by total pips: {winner[0]} ({winner[2]:.0f} pips, {winner[3]:.1f}% WR)")
        if mb_row:
            mb_rank = [r[0] for r in rows].index("market_brain") + 1
            print(f"market_brain rank: {mb_rank} / {len(rows)}")
            print(f"market_brain: {mb_row[2]:.0f} pips, {mb_row[3]:.1f}% WR, sharpe {mb_row[4]:.2f}")

    if args.save_json:
        out = []
        for r in results:
            d = r.to_summary()
            d["strategy"] = r.strategy_name
            out.append(d)
        with open(args.save_json, "w") as f:
            json.dump(out, f, indent=2, default=str)
        print(f"\nFull results JSON: {args.save_json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
