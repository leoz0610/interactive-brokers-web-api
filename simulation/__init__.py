"""
Trading Simulation Package

A comprehensive paper trading and backtesting framework for US stocks
using historical data from Yahoo Finance.
"""

__version__ = "1.0.0"
__author__ = "Interactive Brokers Web API Project"

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies import StrategyBase

from .analytics import PerformanceAnalytics
from .backtest_engine import BacktestEngine
from .data_provider import DataProvider
from .order_manager import Order, OrderManager, OrderSide, OrderStatus, OrderType
from .portfolio_manager import PortfolioManager
from .portfolio_manager_base import PortfolioManagerBase, PositionBase

__all__ = [
    "DataProvider",
    "PortfolioManager",
    "PortfolioManagerBase",
    "PositionBase",
    "OrderManager",
    "Order",
    "OrderType",
    "OrderStatus",
    "OrderSide",
    "BacktestEngine",
    "StrategyBase",
    "PerformanceAnalytics",
]
