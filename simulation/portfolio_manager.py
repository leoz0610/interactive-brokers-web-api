"""
Portfolio Manager Module

Manages portfolio state including cash, positions, and performance tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import logging

from order_manager import Order, OrderSide

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """
    Represents a position in a security.
    """
    symbol: str
    quantity: int
    avg_price: float
    current_price: float = 0.0
    
    @property
    def market_value(self) -> float:
        """Current market value of the position."""
        return self.quantity * self.current_price
    
    @property
    def cost_basis(self) -> float:
        """Total cost basis of the position."""
        return self.quantity * self.avg_price
    
    @property
    def unrealized_pnl(self) -> float:
        """Unrealized profit/loss."""
        return self.market_value - self.cost_basis
    
    @property
    def unrealized_pnl_percent(self) -> float:
        """Unrealized profit/loss as percentage."""
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100
    
    def to_dict(self) -> Dict:
        """Convert position to dictionary."""
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'avg_price': self.avg_price,
            'current_price': self.current_price,
            'market_value': self.market_value,
            'cost_basis': self.cost_basis,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_percent': self.unrealized_pnl_percent,
        }


@dataclass
class Transaction:
    """
    Represents a completed transaction.
    """
    timestamp: datetime
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    commission: float
    order_id: str
    
    @property
    def total_value(self) -> float:
        """Total transaction value including commission."""
        base_value = self.quantity * self.price
        if self.side == OrderSide.BUY:
            return base_value + self.commission
        else:
            return base_value - self.commission
    
    def to_dict(self) -> Dict:
        """Convert transaction to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'side': self.side.value,
            'quantity': self.quantity,
            'price': self.price,
            'commission': self.commission,
            'order_id': self.order_id,
            'total_value': self.total_value,
        }


class PortfolioManager:
    """
    Manages portfolio state and tracks performance.
    """
    
    def __init__(self, initial_cash: float = 100000.0):
        """
        Initialize the PortfolioManager.
        
        Args:
            initial_cash: Starting cash balance
        """
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: Dict[str, Position] = {}
        self.transactions: List[Transaction] = []
        self.equity_history: List[Dict] = []
        
    def process_filled_order(self, order: Order) -> bool:
        """
        Process a filled order and update portfolio.
        
        Args:
            order: Filled order to process
            
        Returns:
            True if order was processed successfully
        """
        if order.filled_price is None or order.filled_quantity == 0:
            logger.error(f"Cannot process unfilled order {order.order_id}")
            return False
        
        trade_value = order.filled_price * order.filled_quantity
        total_cost = trade_value + order.commission
        
        if order.side == OrderSide.BUY:
            # Check if we have enough cash
            if self.cash < total_cost:
                logger.error(
                    f"Insufficient funds: need ${total_cost:.2f}, have ${self.cash:.2f}"
                )
                return False
            
            # Deduct cash
            self.cash -= total_cost
            
            # Update or create position
            if order.symbol in self.positions:
                pos = self.positions[order.symbol]
                total_quantity = pos.quantity + order.filled_quantity
                total_cost_basis = pos.cost_basis + trade_value
                pos.quantity = total_quantity
                pos.avg_price = total_cost_basis / total_quantity
            else:
                self.positions[order.symbol] = Position(
                    symbol=order.symbol,
                    quantity=order.filled_quantity,
                    avg_price=order.filled_price
                )
        
        elif order.side == OrderSide.SELL:
            # Check if we have the position
            if order.symbol not in self.positions:
                logger.error(f"No position in {order.symbol} to sell")
                return False
            
            pos = self.positions[order.symbol]
            if pos.quantity < order.filled_quantity:
                logger.error(
                    f"Insufficient shares: need {order.filled_quantity}, "
                    f"have {pos.quantity}"
                )
                return False
            
            # Add cash from sale
            self.cash += trade_value - order.commission
            
            # Update position
            pos.quantity -= order.filled_quantity
            
            # Remove position if fully closed
            if pos.quantity == 0:
                del self.positions[order.symbol]
        
        # Record transaction
        transaction = Transaction(
            timestamp=order.filled_at or datetime.now(),
            symbol=order.symbol,
            side=order.side,
            quantity=order.filled_quantity,
            price=order.filled_price,
            commission=order.commission,
            order_id=order.order_id
        )
        self.transactions.append(transaction)
        
        logger.info(
            f"Processed {order.side.value} {order.filled_quantity} {order.symbol} "
            f"@ ${order.filled_price:.2f}, cash: ${self.cash:.2f}"
        )
        
        return True
    
    def update_prices(self, prices: Dict[str, float]):
        """
        Update current prices for all positions.
        
        Args:
            prices: Dictionary mapping symbols to current prices
        """
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.current_price = prices[symbol]
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        return self.positions.get(symbol)
    
    def get_all_positions(self) -> List[Position]:
        """Get all positions."""
        return list(self.positions.values())
    
    def get_portfolio_value(self) -> float:
        """
        Calculate total portfolio value (cash + positions).
        
        Returns:
            Total portfolio value
        """
        positions_value = sum(pos.market_value for pos in self.positions.values())
        return self.cash + positions_value
    
    def get_total_pnl(self) -> float:
        """
        Calculate total profit/loss.
        
        Returns:
            Total P&L
        """
        return self.get_portfolio_value() - self.initial_cash
    
    def get_total_pnl_percent(self) -> float:
        """
        Calculate total profit/loss as percentage.
        
        Returns:
            Total P&L percentage
        """
        if self.initial_cash == 0:
            return 0.0
        return (self.get_total_pnl() / self.initial_cash) * 100
    
    def get_realized_pnl(self) -> float:
        """
        Calculate realized profit/loss from closed positions.
        
        Returns:
            Realized P&L
        """
        realized_pnl = 0.0
        
        # Track cost basis for each symbol
        symbol_cost_basis: Dict[str, List[tuple]] = {}
        
        for txn in self.transactions:
            if txn.symbol not in symbol_cost_basis:
                symbol_cost_basis[txn.symbol] = []
            
            if txn.side == OrderSide.BUY:
                # Add to cost basis
                symbol_cost_basis[txn.symbol].append((txn.quantity, txn.price))
            else:
                # Calculate realized P&L using FIFO
                remaining = txn.quantity
                while remaining > 0 and symbol_cost_basis[txn.symbol]:
                    buy_qty, buy_price = symbol_cost_basis[txn.symbol][0]
                    
                    if buy_qty <= remaining:
                        # Fully close this lot
                        realized_pnl += buy_qty * (txn.price - buy_price)
                        remaining -= buy_qty
                        symbol_cost_basis[txn.symbol].pop(0)
                    else:
                        # Partially close this lot
                        realized_pnl += remaining * (txn.price - buy_price)
                        symbol_cost_basis[txn.symbol][0] = (buy_qty - remaining, buy_price)
                        remaining = 0
        
        # Subtract commissions
        total_commissions = sum(txn.commission for txn in self.transactions)
        realized_pnl -= total_commissions
        
        return realized_pnl
    
    def get_unrealized_pnl(self) -> float:
        """
        Calculate unrealized profit/loss from open positions.
        
        Returns:
            Unrealized P&L
        """
        return sum(pos.unrealized_pnl for pos in self.positions.values())
    
    def record_equity(self, timestamp: datetime):
        """
        Record current equity for tracking.
        
        Args:
            timestamp: Current timestamp
        """
        self.equity_history.append({
            'timestamp': timestamp,
            'equity': self.get_portfolio_value(),
            'cash': self.cash,
            'positions_value': sum(p.market_value for p in self.positions.values()),
        })
    
    def get_summary(self) -> Dict:
        """
        Get portfolio summary.
        
        Returns:
            Dictionary with portfolio metrics
        """
        return {
            'cash': self.cash,
            'positions_value': sum(p.market_value for p in self.positions.values()),
            'total_value': self.get_portfolio_value(),
            'initial_cash': self.initial_cash,
            'total_pnl': self.get_total_pnl(),
            'total_pnl_percent': self.get_total_pnl_percent(),
            'realized_pnl': self.get_realized_pnl(),
            'unrealized_pnl': self.get_unrealized_pnl(),
            'num_positions': len(self.positions),
            'num_transactions': len(self.transactions),
        }
