"""
Portfolio Manager Base Module

Abstract base class for portfolio management implementations.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional

from order_manager import Order


class PositionBase(ABC):
    """
    Abstract base class representing a position in a security.
    """

    @property
    @abstractmethod
    def symbol(self) -> str:
        """Symbol of the position."""
        pass

    @property
    @abstractmethod
    def quantity(self) -> int:
        """Quantity of shares held."""
        pass

    @property
    @abstractmethod
    def avg_price(self) -> float:
        """Average price of the position."""
        pass

    @property
    @abstractmethod
    def current_price(self) -> float:
        """Current market price."""
        pass

    @property
    @abstractmethod
    def market_value(self) -> float:
        """Current market value of the position."""
        pass

    @property
    @abstractmethod
    def cost_basis(self) -> float:
        """Total cost basis of the position."""
        pass

    @property
    @abstractmethod
    def unrealized_pnl(self) -> float:
        """Unrealized profit/loss."""
        pass

    @property
    @abstractmethod
    def unrealized_pnl_percent(self) -> float:
        """Unrealized profit/loss as percentage."""
        pass

    @abstractmethod
    def to_dict(self) -> Dict:
        """Convert position to dictionary."""
        pass


class PortfolioManagerBase(ABC):
    """
    Abstract base class for portfolio management.

    This interface allows strategies to access either simulated or
    live (e.g., IBKR) portfolio managers using the same interface.
    """

    @property
    @abstractmethod
    def cash(self) -> float:
        """Current cash balance."""
        pass

    @property
    @abstractmethod
    def initial_cash(self) -> float:
        """Initial cash balance."""
        pass

    @abstractmethod
    def process_filled_order(self, order: Order) -> bool:
        """
        Process a filled order and update portfolio.

        Args:
            order: Filled order to process

        Returns:
            True if order was processed successfully
        """
        pass

    @abstractmethod
    def update_prices(self, prices: Dict[str, float]) -> None:
        """
        Update current prices for all positions.

        Args:
            prices: Dictionary mapping symbols to current prices
        """
        pass

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[PositionBase]:
        """
        Get position for a symbol.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Position object or None if no position
        """
        pass

    @abstractmethod
    def get_all_positions(self) -> List[PositionBase]:
        """
        Get all positions.

        Returns:
            List of all position objects
        """
        pass

    @abstractmethod
    def get_portfolio_value(self) -> float:
        """
        Calculate total portfolio value (cash + positions).

        Returns:
            Total portfolio value
        """
        pass

    @abstractmethod
    def get_total_pnl(self) -> float:
        """
        Calculate total profit/loss.

        Returns:
            Total P&L
        """
        pass

    @abstractmethod
    def get_total_pnl_percent(self) -> float:
        """
        Calculate total profit/loss as percentage.

        Returns:
            Total P&L percentage
        """
        pass

    @abstractmethod
    def get_realized_pnl(self) -> float:
        """
        Calculate realized profit/loss from closed positions.

        Returns:
            Realized P&L
        """
        pass

    @abstractmethod
    def get_unrealized_pnl(self) -> float:
        """
        Calculate unrealized profit/loss from open positions.

        Returns:
            Unrealized P&L
        """
        pass

    @abstractmethod
    def record_equity(self, timestamp: datetime) -> None:
        """
        Record current equity for tracking.

        Args:
            timestamp: Current timestamp
        """
        pass

    @abstractmethod
    def get_summary(self) -> Dict:
        """
        Get portfolio summary.

        Returns:
            Dictionary with portfolio metrics
        """
        pass
