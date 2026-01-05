"""
Strategy Base Module

Abstract base class for implementing trading strategies.
"""

import os
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from ..order_manager import Order, OrderSide, OrderType
from ..portfolio_manager_base import PortfolioManagerBase


class StrategyBase(ABC):
    """
    Abstract base class for trading strategies.

    Subclasses must implement the on_data() method to define trading logic.
    """

    def __init__(self, name: str = "Strategy"):
        """
        Initialize the strategy.

        Args:
            name: Strategy name
        """
        self.name = name
        self.portfolio: Optional[PortfolioManagerBase] = None
        self.current_time: Optional[datetime] = None
        self.data_cache: Dict[str, pd.DataFrame] = {}

    def set_portfolio(self, portfolio: PortfolioManagerBase):
        """
        Set the portfolio manager.

        Args:
            portfolio: PortfolioManagerBase instance
        """
        self.portfolio = portfolio

    def set_data(self, symbol: str, data: pd.DataFrame):
        """
        Set historical data for a symbol.

        Args:
            symbol: Stock ticker symbol
            data: Historical OHLCV data
        """
        self.data_cache[symbol] = data

    @abstractmethod
    def on_data(self, timestamp: datetime, data: Dict[str, pd.DataFrame]) -> List[Dict]:
        """
        Called on each time step with current market data.

        Subclasses must implement this method to generate trading signals.

        Args:
            timestamp: Current timestamp
            data: Dictionary mapping symbols to DataFrames with historical data
                  up to the current timestamp

        Returns:
            List of order dictionaries with keys:
                - symbol: str
                - side: 'BUY' or 'SELL'
                - quantity: int
                - order_type: 'MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT'
                - limit_price: float (optional)
                - stop_price: float (optional)
        """
        pass

    def on_start(self):
        """
        Called once at the start of the backtest.

        Override this method to perform initialization.
        """
        pass

    def on_end(self):
        """
        Called once at the end of the backtest.

        Override this method to perform cleanup or final calculations.
        """
        pass

    def get_position_size(
        self, symbol: str, price: float, risk_percent: float = 2.0
    ) -> int:
        """
        Calculate position size based on risk management.

        Args:
            symbol: Stock ticker symbol
            price: Current price
            risk_percent: Percentage of portfolio to risk

        Returns:
            Number of shares to trade
        """
        if not self.portfolio:
            return 0

        portfolio_value = self.portfolio.get_portfolio_value()
        risk_amount = portfolio_value * (risk_percent / 100)

        # Simple position sizing: risk amount divided by price
        shares = int(risk_amount / price)

        return max(shares, 0)

    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for a symbol.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Current close price or None
        """
        if symbol not in self.data_cache:
            return None

        data = self.data_cache[symbol]
        if self.current_time is None or data.empty:
            return None

        # Get data up to current time
        current_data = data[data.index <= self.current_time]
        if current_data.empty:
            return None

        return float(current_data["Close"].iloc[-1])

    def get_historical_data(
        self, symbol: str, lookback_periods: int = 100
    ) -> Optional[pd.DataFrame]:
        """
        Get historical data for a symbol up to current time.

        Args:
            symbol: Stock ticker symbol
            lookback_periods: Number of periods to look back

        Returns:
            DataFrame with historical data or None
        """
        if symbol not in self.data_cache:
            return None

        data = self.data_cache[symbol]
        if self.current_time is None or data.empty:
            return None

        # Get data up to current time
        current_data = data[data.index <= self.current_time]

        # Return last N periods
        return current_data.tail(lookback_periods)

    def has_position(self, symbol: str) -> bool:
        """
        Check if we have a position in a symbol.

        Args:
            symbol: Stock ticker symbol

        Returns:
            True if position exists
        """
        if not self.portfolio:
            return False

        position = self.portfolio.get_position(symbol)
        return position is not None and position.quantity > 0

    def get_position_quantity(self, symbol: str) -> int:
        """
        Get current position quantity.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Number of shares held
        """
        if not self.portfolio:
            return 0

        position = self.portfolio.get_position(symbol)
        return position.quantity if position else 0

    def create_market_order(self, symbol: str, side: str, quantity: int) -> Dict:
        """
        Helper to create a market order.

        Args:
            symbol: Stock ticker symbol
            side: 'BUY' or 'SELL'
            quantity: Number of shares

        Returns:
            Order dictionary
        """
        return {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": "MARKET",
        }

    def create_limit_order(
        self, symbol: str, side: str, quantity: int, limit_price: float
    ) -> Dict:
        """
        Helper to create a limit order.

        Args:
            symbol: Stock ticker symbol
            side: 'BUY' or 'SELL'
            quantity: Number of shares
            limit_price: Limit price

        Returns:
            Order dictionary
        """
        return {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": "LIMIT",
            "limit_price": limit_price,
        }
