"""
Trading Library Package

A comprehensive paper trading and backtesting framework for US stocks
using historical data from Yahoo Finance.
"""

__version__ = "1.0.0"
__author__ = "Interactive Brokers Web API Project"

from .analytics import PerformanceAnalytics
from .backtest_engine import BacktestEngine
from .data_provider import DataProvider
from .order_manager import Order, OrderManager, OrderSide, OrderStatus, OrderType
from .portfolio_manager import PortfolioManager
from .portfolio_manager_base import PortfolioManagerBase, PositionBase
from .strategies import StrategyBase

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
