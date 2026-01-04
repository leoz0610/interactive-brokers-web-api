"""
Order Manager Module

Handles order placement, execution, and management in the simulation.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict
import uuid
import logging

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """Order types supported by the simulation."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderSide(Enum):
    """Order side (buy or sell)."""
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    """Order status."""
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    """
    Represents a trading order.
    """
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: OrderStatus = OrderStatus.PENDING
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    filled_quantity: int = 0
    filled_price: Optional[float] = None
    commission: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate order parameters."""
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("Limit price required for limit orders")
        
        if self.order_type == OrderType.STOP and self.stop_price is None:
            raise ValueError("Stop price required for stop orders")
        
        if self.order_type == OrderType.STOP_LIMIT:
            if self.limit_price is None or self.stop_price is None:
                raise ValueError("Both limit and stop prices required for stop-limit orders")
    
    def to_dict(self) -> Dict:
        """Convert order to dictionary."""
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'quantity': self.quantity,
            'order_type': self.order_type.value,
            'status': self.status.value,
            'limit_price': self.limit_price,
            'stop_price': self.stop_price,
            'filled_quantity': self.filled_quantity,
            'filled_price': self.filled_price,
            'commission': self.commission,
            'created_at': self.created_at.isoformat(),
            'filled_at': self.filled_at.isoformat() if self.filled_at else None,
        }


class OrderManager:
    """
    Manages order execution and tracking.
    """
    
    def __init__(
        self,
        commission_per_share: float = 0.0,
        commission_percent: float = 0.0,
        slippage_percent: float = 0.0
    ):
        """
        Initialize the OrderManager.
        
        Args:
            commission_per_share: Commission charged per share
            commission_percent: Commission as percentage of trade value
            slippage_percent: Slippage as percentage of price
        """
        self.orders: Dict[str, Order] = {}
        self.commission_per_share = commission_per_share
        self.commission_percent = commission_percent
        self.slippage_percent = slippage_percent
        
    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Order:
        """
        Create a new order.
        
        Args:
            symbol: Stock ticker symbol
            side: Buy or sell
            quantity: Number of shares
            order_type: Type of order
            limit_price: Limit price (for limit orders)
            stop_price: Stop price (for stop orders)
            
        Returns:
            Created Order object
        """
        order = Order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price
        )
        
        self.orders[order.order_id] = order
        logger.info(f"Created order {order.order_id}: {side.value} {quantity} {symbol}")
        
        return order
    
    def execute_order(
        self,
        order: Order,
        current_price: float,
        current_time: datetime
    ) -> bool:
        """
        Attempt to execute an order at the current price.
        
        Args:
            order: Order to execute
            current_price: Current market price
            current_time: Current simulation time
            
        Returns:
            True if order was executed
        """
        if order.status != OrderStatus.PENDING:
            return False
        
        # Check if order should be executed based on type
        should_execute = False
        execution_price = current_price
        
        if order.order_type == OrderType.MARKET:
            should_execute = True
            # Apply slippage for market orders
            if order.side == OrderSide.BUY:
                execution_price *= (1 + self.slippage_percent / 100)
            else:
                execution_price *= (1 - self.slippage_percent / 100)
        
        elif order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY and current_price <= order.limit_price:
                should_execute = True
                execution_price = order.limit_price
            elif order.side == OrderSide.SELL and current_price >= order.limit_price:
                should_execute = True
                execution_price = order.limit_price
        
        elif order.order_type == OrderType.STOP:
            if order.side == OrderSide.BUY and current_price >= order.stop_price:
                should_execute = True
            elif order.side == OrderSide.SELL and current_price <= order.stop_price:
                should_execute = True
        
        elif order.order_type == OrderType.STOP_LIMIT:
            # Stop triggered, check limit
            if order.side == OrderSide.BUY:
                if current_price >= order.stop_price and current_price <= order.limit_price:
                    should_execute = True
                    execution_price = order.limit_price
            else:
                if current_price <= order.stop_price and current_price >= order.limit_price:
                    should_execute = True
                    execution_price = order.limit_price
        
        if should_execute:
            # Calculate commission
            trade_value = execution_price * order.quantity
            commission = (
                self.commission_per_share * order.quantity +
                trade_value * self.commission_percent / 100
            )
            
            # Fill the order
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.filled_price = execution_price
            order.commission = commission
            order.filled_at = current_time
            
            logger.info(
                f"Executed order {order.order_id}: {order.side.value} "
                f"{order.quantity} {order.symbol} @ ${execution_price:.2f}"
            )
            
            return True
        
        return False
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.
        
        Args:
            order_id: ID of order to cancel
            
        Returns:
            True if order was cancelled
        """
        if order_id not in self.orders:
            return False
        
        order = self.orders[order_id]
        if order.status == OrderStatus.PENDING:
            order.status = OrderStatus.CANCELLED
            logger.info(f"Cancelled order {order_id}")
            return True
        
        return False
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self.orders.get(order_id)
    
    def get_pending_orders(self) -> List[Order]:
        """Get all pending orders."""
        return [o for o in self.orders.values() if o.status == OrderStatus.PENDING]
    
    def get_filled_orders(self) -> List[Order]:
        """Get all filled orders."""
        return [o for o in self.orders.values() if o.status == OrderStatus.FILLED]
    
    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        """Get all orders for a specific symbol."""
        return [o for o in self.orders.values() if o.symbol == symbol]
    
    def get_all_orders(self) -> List[Order]:
        """Get all orders."""
        return list(self.orders.values())
