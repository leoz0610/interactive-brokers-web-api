"""
Trading Strategies Package

Collection of example trading strategies.
"""

from .buy_and_hold import BuyAndHoldStrategy
from .moving_average import MovingAverageCrossoverStrategy

__all__ = [
    "BuyAndHoldStrategy",
    "MovingAverageCrossoverStrategy",
]
