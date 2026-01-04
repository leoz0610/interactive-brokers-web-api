"""
Trading Strategies Package

Collection of trading strategies for backtesting and live trading.
"""

from .buy_and_hold import BuyAndHoldStrategy
from .moving_average import MovingAverageCrossoverStrategy
from .strategy_base import StrategyBase

__all__ = [
    "StrategyBase",
    "BuyAndHoldStrategy",
    "MovingAverageCrossoverStrategy",
]
