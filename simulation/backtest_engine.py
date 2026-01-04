"""
Backtest Engine Module

Core engine for running backtests with trading strategies.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import logging

from data_provider import DataProvider
from portfolio_manager import PortfolioManager
from order_manager import OrderManager, OrderType, OrderSide
from strategy_base import StrategyBase
from analytics import PerformanceAnalytics

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Event-driven backtesting engine.
    """
    
    def __init__(
        self,
        initial_cash: float = 100000.0,
        commission_per_share: float = 0.0,
        commission_percent: float = 0.0,
        slippage_percent: float = 0.1
    ):
        """
        Initialize the BacktestEngine.
        
        Args:
            initial_cash: Starting capital
            commission_per_share: Commission per share
            commission_percent: Commission as percentage
            slippage_percent: Slippage as percentage
        """
        self.initial_cash = initial_cash
        self.data_provider = DataProvider()
        self.portfolio = PortfolioManager(initial_cash)
        self.order_manager = OrderManager(
            commission_per_share=commission_per_share,
            commission_percent=commission_percent,
            slippage_percent=slippage_percent
        )
        self.strategy: Optional[StrategyBase] = None
        self.market_data: Dict[str, pd.DataFrame] = {}
        self.symbols: List[str] = []
        self.start_date: Optional[str] = None
        self.end_date: Optional[str] = None
        
    def set_strategy(self, strategy: StrategyBase):
        """
        Set the trading strategy.
        
        Args:
            strategy: StrategyBase instance
        """
        self.strategy = strategy
        self.strategy.set_portfolio(self.portfolio)
        logger.info(f"Strategy set: {strategy.name}")
    
    def load_data(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        interval: str = "1d"
    ):
        """
        Load historical data for backtesting.
        
        Args:
            symbols: List of stock symbols
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            interval: Data interval
        """
        self.symbols = symbols
        self.start_date = start_date
        self.end_date = end_date
        
        logger.info(f"Loading data for {len(symbols)} symbols from {start_date} to {end_date}")
        
        self.market_data = self.data_provider.get_multiple_symbols(
            symbols, start_date, end_date, interval
        )
        
        # Set data in strategy
        if self.strategy:
            for symbol, data in self.market_data.items():
                self.strategy.set_data(symbol, data)
        
        logger.info(f"Loaded data for {len(self.market_data)} symbols")
    
    def run(self) -> Dict:
        """
        Run the backtest.
        
        Returns:
            Dictionary with backtest results
        """
        if not self.strategy:
            raise ValueError("Strategy not set. Call set_strategy() first.")
        
        if not self.market_data:
            raise ValueError("No data loaded. Call load_data() first.")
        
        logger.info(f"Starting backtest: {self.strategy.name}")
        
        # Call strategy initialization
        self.strategy.on_start()
        
        # Get all unique timestamps across all symbols
        all_timestamps = set()
        for data in self.market_data.values():
            all_timestamps.update(data.index)
        
        timestamps = sorted(all_timestamps)
        logger.info(f"Backtesting over {len(timestamps)} time periods")
        
        # Main backtest loop
        for i, timestamp in enumerate(timestamps):
            self.strategy.current_time = timestamp
            
            # Get current prices for all symbols
            current_prices = {}
            for symbol, data in self.market_data.items():
                if timestamp in data.index:
                    current_prices[symbol] = float(data.loc[timestamp, 'Close'])
            
            # Update portfolio prices
            self.portfolio.update_prices(current_prices)
            
            # Process pending orders
            pending_orders = self.order_manager.get_pending_orders()
            for order in pending_orders:
                if order.symbol in current_prices:
                    executed = self.order_manager.execute_order(
                        order,
                        current_prices[order.symbol],
                        timestamp
                    )
                    
                    if executed:
                        # Update portfolio
                        self.portfolio.process_filled_order(order)
            
            # Get data up to current timestamp for strategy
            strategy_data = {}
            for symbol, data in self.market_data.items():
                strategy_data[symbol] = data[data.index <= timestamp]
            
            # Call strategy to generate signals
            try:
                signals = self.strategy.on_data(timestamp, strategy_data)
                
                # Process signals and create orders
                if signals:
                    for signal in signals:
                        self._process_signal(signal, current_prices)
                        
            except Exception as e:
                logger.error(f"Strategy error at {timestamp}: {e}")
            
            # Record equity
            self.portfolio.record_equity(timestamp)
            
            # Log progress
            if (i + 1) % 50 == 0 or i == len(timestamps) - 1:
                pnl_pct = self.portfolio.get_total_pnl_percent()
                logger.info(
                    f"Progress: {i+1}/{len(timestamps)} ({(i+1)/len(timestamps)*100:.1f}%) "
                    f"- P&L: {pnl_pct:+.2f}%"
                )
        
        # Call strategy cleanup
        self.strategy.on_end()
        
        logger.info("Backtest completed")
        
        # Generate results
        results = self._generate_results()
        
        return results
    
    def _process_signal(self, signal: Dict, current_prices: Dict[str, float]):
        """
        Process a trading signal and create an order.
        
        Args:
            signal: Signal dictionary from strategy
            current_prices: Current market prices
        """
        try:
            symbol = signal['symbol']
            side_str = signal['side'].upper()
            quantity = signal['quantity']
            order_type_str = signal.get('order_type', 'MARKET').upper()
            
            # Convert strings to enums
            side = OrderSide.BUY if side_str == 'BUY' else OrderSide.SELL
            order_type = OrderType[order_type_str]
            
            # Validate we have price data
            if symbol not in current_prices:
                logger.warning(f"No price data for {symbol}, skipping order")
                return
            
            # Create order
            order = self.order_manager.create_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=signal.get('limit_price'),
                stop_price=signal.get('stop_price')
            )
            
            # Try to execute immediately if market order
            if order_type == OrderType.MARKET:
                executed = self.order_manager.execute_order(
                    order,
                    current_prices[symbol],
                    self.strategy.current_time
                )
                
                if executed:
                    self.portfolio.process_filled_order(order)
                    
        except Exception as e:
            logger.error(f"Failed to process signal: {e}")
    
    def _generate_results(self) -> Dict:
        """
        Generate backtest results and statistics.
        
        Returns:
            Dictionary with results
        """
        # Calculate analytics
        analytics = PerformanceAnalytics(
            equity_history=self.portfolio.equity_history,
            transactions=self.portfolio.transactions,
            initial_cash=self.initial_cash
        )
        
        metrics = analytics.calculate_metrics()
        
        # Combine with portfolio summary
        results = {
            'strategy': self.strategy.name,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'symbols': self.symbols,
            'portfolio_summary': self.portfolio.get_summary(),
            'performance_metrics': metrics,
            'equity_curve': self.portfolio.equity_history,
            'transactions': [t.to_dict() for t in self.portfolio.transactions],
            'final_positions': [p.to_dict() for p in self.portfolio.get_all_positions()],
            'orders': [o.to_dict() for o in self.order_manager.get_all_orders()],
        }
        
        return results
    
    def get_equity_curve(self) -> pd.DataFrame:
        """
        Get equity curve as DataFrame.
        
        Returns:
            DataFrame with timestamp and equity columns
        """
        if not self.portfolio.equity_history:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.portfolio.equity_history)
        df.set_index('timestamp', inplace=True)
        return df
