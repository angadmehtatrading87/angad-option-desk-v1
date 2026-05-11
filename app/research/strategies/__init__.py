"""Reference strategies for the backtester."""

from app.research.strategies.donchian import DonchianBreakout
from app.research.strategies.bollinger import BollingerMeanRevert
from app.research.strategies.ma_crossover import MACrossover
from app.research.strategies.market_brain_strategy import MarketBrainStrategy

REGISTRY = {
    "donchian": DonchianBreakout,
    "bollinger": BollingerMeanRevert,
    "ma_crossover": MACrossover,
    "market_brain": MarketBrainStrategy,
}
