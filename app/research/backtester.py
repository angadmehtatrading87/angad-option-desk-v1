"""
Backtester core.

Replays historical bars through a Strategy, simulating fills at the close
of the signaling bar. Tracks equity, per-trade P&L, drawdown, and produces
a summary report.

Limitations (deliberate for v1):
    - Mark-to-market at close only (no intra-bar fills)
    - Fixed position sizing (1 lot per trade — equity expressed as pip P&L)
    - No spread / slippage model yet (TODO: feed from cost_cap context)
    - No multi-position support (one position at a time per strategy)

That's enough to compare strategy performance reliably; for live-fidelity
we'd add bid/ask spread, slippage, and partial-fill modeling later.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.research.data_loader import Bar, load_bars
from app.research.strategy_base import Signal, Strategy


@dataclass
class Trade:
    entry_ts: datetime
    exit_ts: datetime | None
    direction: str           # "long" or "short"
    entry_price: float
    exit_price: float | None
    pnl_pips: float | None
    rationale_in: str
    rationale_out: str = ""

    def is_open(self) -> bool:
        return self.exit_ts is None


@dataclass
class BacktestResult:
    strategy_name: str
    symbol: str
    interval: str
    start: datetime
    end: datetime
    bar_count: int
    trades: list[Trade] = field(default_factory=list)
    final_equity_pips: float = 0.0
    max_drawdown_pips: float = 0.0
    win_rate: float = 0.0
    avg_win_pips: float = 0.0
    avg_loss_pips: float = 0.0
    profit_factor: float = 0.0
    sharpe: float = 0.0

    def to_summary(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy_name,
            "symbol": self.symbol,
            "interval": self.interval,
            "bars": self.bar_count,
            "trades": len([t for t in self.trades if not t.is_open()]),
            "final_pips": round(self.final_equity_pips, 1),
            "max_drawdown_pips": round(self.max_drawdown_pips, 1),
            "win_rate_pct": round(self.win_rate * 100.0, 1),
            "avg_win_pips": round(self.avg_win_pips, 1),
            "avg_loss_pips": round(self.avg_loss_pips, 1),
            "profit_factor": round(self.profit_factor, 2),
            "sharpe": round(self.sharpe, 2),
        }


def _pip_size(symbol: str) -> float:
    """USDJPY (and JPY pairs in general) quote in 0.01; everything else in 0.0001."""
    return 0.01 if "JPY" in symbol.upper() else 0.0001


def run_backtest(
    strategy: Strategy,
    symbol: str,
    interval: str = "1H",
    start: datetime | None = None,
    end: datetime | None = None,
) -> BacktestResult:
    bars: list[Bar] = load_bars(symbol, interval, start=start, end=end)
    if not bars:
        return BacktestResult(
            strategy_name=getattr(strategy, "name", strategy.__class__.__name__),
            symbol=symbol, interval=interval,
            start=start or datetime.min, end=end or datetime.max,
            bar_count=0,
        )

    pip = _pip_size(symbol)
    state: dict[str, Any] = {}
    open_trade: Trade | None = None
    closed_trades: list[Trade] = []
    # Realized-only equity curve: only updated when a trade closes.
    # We separately track unrealized for drawdown.
    realized_equity: float = 0.0
    equity_curve: list[float] = [0.0]
    peak_with_unrealized: float = 0.0
    max_dd_with_unrealized: float = 0.0

    for bar in bars:
        signal: Signal | None = strategy.on_bar(bar, state)

        # Mark-to-market unrealized for drawdown
        if open_trade is not None:
            if open_trade.direction == "long":
                unreal = (bar.close - open_trade.entry_price) / pip
            else:
                unreal = (open_trade.entry_price - bar.close) / pip
            current_eq = realized_equity + unreal
        else:
            current_eq = realized_equity
        peak_with_unrealized = max(peak_with_unrealized, current_eq)
        max_dd_with_unrealized = max(max_dd_with_unrealized, peak_with_unrealized - current_eq)

        if signal is None:
            continue

        if signal.direction in ("long", "short"):
            if open_trade is not None:
                closed = _close_trade(open_trade, bar, pip, "flip-to-" + signal.direction)
                closed_trades.append(closed)
                realized_equity += float(closed.pnl_pips or 0.0)
                equity_curve.append(realized_equity)
                open_trade = None
            open_trade = Trade(
                entry_ts=bar.ts,
                exit_ts=None,
                direction=signal.direction,
                entry_price=float(bar.close),
                exit_price=None,
                pnl_pips=None,
                rationale_in=signal.rationale,
            )
        elif signal.direction == "exit" and open_trade is not None:
            closed = _close_trade(open_trade, bar, pip, signal.rationale)
            closed_trades.append(closed)
            realized_equity += float(closed.pnl_pips or 0.0)
            equity_curve.append(realized_equity)
            open_trade = None

    # Close any still-open trade at the last bar so the result is final.
    if open_trade is not None and bars:
        closed = _close_trade(open_trade, bars[-1], pip, "backtest-end-mark-out")
        closed_trades.append(closed)
        realized_equity += float(closed.pnl_pips or 0.0)
        equity_curve.append(realized_equity)

    return _summarize(
        strategy_name=getattr(strategy, "name", strategy.__class__.__name__),
        symbol=symbol, interval=interval,
        start=bars[0].ts, end=bars[-1].ts,
        bar_count=len(bars),
        trades=closed_trades,
        equity_curve=equity_curve,
        max_dd_override=max_dd_with_unrealized,
    )


def _close_trade(trade: Trade, bar: Bar, pip: float, exit_reason: str) -> Trade:
    if trade.direction == "long":
        pnl = (bar.close - trade.entry_price) / pip
    else:
        pnl = (trade.entry_price - bar.close) / pip
    return Trade(
        entry_ts=trade.entry_ts,
        exit_ts=bar.ts,
        direction=trade.direction,
        entry_price=trade.entry_price,
        exit_price=float(bar.close),
        pnl_pips=round(pnl, 2),
        rationale_in=trade.rationale_in,
        rationale_out=exit_reason,
    )


def _summarize(
    strategy_name: str, symbol: str, interval: str,
    start: datetime, end: datetime, bar_count: int,
    trades: list[Trade], equity_curve: list[float],
    max_dd_override: float | None = None,
) -> BacktestResult:
    pnls = [t.pnl_pips for t in trades if t.pnl_pips is not None]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    win_rate = (len(wins) / len(pnls)) if pnls else 0.0
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0
    pf = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else (math.inf if wins else 0.0)

    # Sharpe: mean / stdev of per-trade pip returns. Not annualized; this is
    # a relative-comparison metric across strategies.
    if len(pnls) >= 2:
        try:
            mean_p = statistics.mean(pnls)
            std_p = statistics.pstdev(pnls)
            sharpe = mean_p / std_p if std_p > 0 else 0.0
        except Exception:
            sharpe = 0.0
    else:
        sharpe = 0.0

    # Max drawdown — prefer the unrealized-aware override since the live
    # bot would have seen those losses on screen.
    if max_dd_override is not None:
        max_dd = max_dd_override
    elif equity_curve:
        peak = equity_curve[0]
        max_dd = 0.0
        for eq in equity_curve:
            peak = max(peak, eq)
            dd = peak - eq
            max_dd = max(max_dd, dd)
    else:
        max_dd = 0.0

    # Final equity = sum of realized trade pnls (authoritative).
    final_equity = sum(p for p in pnls) if pnls else 0.0

    return BacktestResult(
        strategy_name=strategy_name,
        symbol=symbol, interval=interval,
        start=start, end=end,
        bar_count=bar_count,
        trades=trades,
        final_equity_pips=final_equity,
        max_drawdown_pips=max_dd,
        win_rate=win_rate,
        avg_win_pips=avg_win,
        avg_loss_pips=avg_loss,
        profit_factor=pf if pf != math.inf else 999.0,
        sharpe=sharpe,
    )
