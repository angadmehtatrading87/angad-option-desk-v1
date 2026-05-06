"""
Research / backtesting subsystem.

Lets us replay historical FX OHLC data through:
    - The bot's existing market_brain scoring
    - Reference public-domain strategies (Donchian, Bollinger, MA cross)

So we can see what scores look like on real moves vs flat days, tune
thresholds against the actual signal distribution, and benchmark whether
market_brain is competitive vs textbook strategies.

Run a backtest:
    python -m app.research.cli --symbol EURUSD --strategy donchian \\
        --start 2024-01-01 --end 2024-12-31

The CLI prints equity curve summary + per-trade log + Sharpe / win-rate /
max drawdown.

Historical data lives under `data/historical/<SYMBOL>_<INTERVAL>.csv`.
Use `cleanup/download_fx_history.sh` to populate it.
"""
