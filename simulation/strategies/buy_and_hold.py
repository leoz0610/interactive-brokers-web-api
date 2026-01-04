"""
Buy and Hold Strategy

Simple strategy that buys on the first day and holds until the end.
"""

from datetime import datetime
from typing import Dict, List
import pandas as pd

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy_base import StrategyBase


class BuyAndHoldStrategy(StrategyBase):
    """
    Buy and hold strategy - buys all symbols on first day and holds.
    """
    
    def __init__(self, allocation_per_symbol: float = 0.9):
        """
        Initialize the strategy.
        
        Args:
            allocation_per_symbol: Fraction of portfolio to allocate per symbol
        """
        super().__init__(name="Buy and Hold")
        self.allocation_per_symbol = allocation_per_symbol
        self.has_bought = False
    
    def on_data(
        self,
        timestamp: datetime,
        data: Dict[str, pd.DataFrame]
    ) -> List[Dict]:
        """
        Generate trading signals.
        
        Buy all symbols on first call, then hold.
        """
        # Only buy once at the start
        if self.has_bought:
            return []
        
        signals = []
        
        # Calculate how much to invest per symbol
        portfolio_value = self.portfolio.get_portfolio_value()
        allocation_per_symbol = portfolio_value * self.allocation_per_symbol / len(data)
        
        for symbol, df in data.items():
            if df.empty:
                continue
            
            # Get current price
            current_price = float(df['Close'].iloc[-1])
            
            # Calculate quantity
            quantity = int(allocation_per_symbol / current_price)
            
            if quantity > 0:
                signals.append(self.create_market_order(
                    symbol=symbol,
                    side='BUY',
                    quantity=quantity
                ))
        
        self.has_bought = True
        
        return signals
