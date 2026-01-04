"""
Moving Average Crossover Strategy

Generates buy signals when fast MA crosses above slow MA,
and sell signals when fast MA crosses below slow MA.
"""

from datetime import datetime
from typing import Dict, List
import pandas as pd

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy_base import StrategyBase


class MovingAverageCrossoverStrategy(StrategyBase):
    """
    Moving average crossover strategy.
    
    Buys when fast MA crosses above slow MA.
    Sells when fast MA crosses below slow MA.
    """
    
    def __init__(
        self,
        fast_period: int = 20,
        slow_period: int = 50,
        position_size_pct: float = 20.0
    ):
        """
        Initialize the strategy.
        
        Args:
            fast_period: Fast moving average period
            slow_period: Slow moving average period
            position_size_pct: Percentage of portfolio per position
        """
        super().__init__(name=f"MA Crossover ({fast_period}/{slow_period})")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.position_size_pct = position_size_pct
        self.previous_signals = {}
    
    def on_data(
        self,
        timestamp: datetime,
        data: Dict[str, pd.DataFrame]
    ) -> List[Dict]:
        """
        Generate trading signals based on MA crossover.
        """
        signals = []
        
        for symbol, df in data.items():
            if len(df) < self.slow_period:
                continue
            
            # Calculate moving averages
            fast_ma = df['Close'].rolling(window=self.fast_period).mean()
            slow_ma = df['Close'].rolling(window=self.slow_period).mean()
            
            # Get current and previous values
            if len(fast_ma) < 2 or len(slow_ma) < 2:
                continue
            
            current_fast = fast_ma.iloc[-1]
            current_slow = slow_ma.iloc[-1]
            prev_fast = fast_ma.iloc[-2]
            prev_slow = slow_ma.iloc[-2]
            
            # Skip if any value is NaN
            if pd.isna(current_fast) or pd.isna(current_slow):
                continue
            if pd.isna(prev_fast) or pd.isna(prev_slow):
                continue
            
            current_price = float(df['Close'].iloc[-1])
            
            # Detect crossover
            bullish_cross = prev_fast <= prev_slow and current_fast > current_slow
            bearish_cross = prev_fast >= prev_slow and current_fast < current_slow
            
            # Generate signals
            if bullish_cross and not self.has_position(symbol):
                # Buy signal
                portfolio_value = self.portfolio.get_portfolio_value()
                position_value = portfolio_value * (self.position_size_pct / 100)
                quantity = int(position_value / current_price)
                
                if quantity > 0:
                    signals.append(self.create_market_order(
                        symbol=symbol,
                        side='BUY',
                        quantity=quantity
                    ))
                    self.previous_signals[symbol] = 'BUY'
            
            elif bearish_cross and self.has_position(symbol):
                # Sell signal
                quantity = self.get_position_quantity(symbol)
                
                if quantity > 0:
                    signals.append(self.create_market_order(
                        symbol=symbol,
                        side='SELL',
                        quantity=quantity
                    ))
                    self.previous_signals[symbol] = 'SELL'
        
        return signals
