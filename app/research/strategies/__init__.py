"""Reference strategies for the backtester."""

from app.research.strategies.donchian import DonchianBreakout
from app.research.strategies.bollinger import BollingerMeanRevert
from app.research.strategies.ma_crossover import MACrossover

REGISTRY = {
    "donchian": DonchianBreakout,
    "bollinger": BollingerMeanRevert,
    "ma_crossover": MACrossover,
}
