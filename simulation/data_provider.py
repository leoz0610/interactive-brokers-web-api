"""
Data Provider Module

Fetches and caches historical market data from Yahoo Finance.
"""

import os
import json
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataProvider:
    """
    Provides historical market data from Yahoo Finance with caching capabilities.
    """
    
    def __init__(self, cache_dir: str = "simulation/data/cache"):
        """
        Initialize the DataProvider.
        
        Args:
            cache_dir: Directory to store cached data
        """
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
    def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data for a symbol.
        
        Args:
            symbol: Stock ticker symbol
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            interval: Data interval (1d, 1h, etc.)
            use_cache: Whether to use cached data if available
            
        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume, Adj Close
        """
        cache_file = self._get_cache_filename(symbol, start_date, end_date, interval)
        
        # Try to load from cache
        if use_cache and os.path.exists(cache_file):
            try:
                df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                logger.info(f"Loaded {symbol} data from cache")
                return df
            except Exception as e:
                logger.warning(f"Failed to load cache for {symbol}: {e}")
        
        # Fetch from Yahoo Finance
        try:
            logger.info(f"Fetching {symbol} data from Yahoo Finance...")
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date, interval=interval)
            
            if df.empty:
                raise ValueError(f"No data returned for {symbol}")
            
            # Save to cache
            df.to_csv(cache_file)
            logger.info(f"Cached {symbol} data with {len(df)} rows")
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            raise
    
    def get_multiple_symbols(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        interval: str = "1d"
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical data for multiple symbols.
        
        Args:
            symbols: List of stock ticker symbols
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            interval: Data interval
            
        Returns:
            Dictionary mapping symbols to DataFrames
        """
        data = {}
        for symbol in symbols:
            try:
                df = self.get_historical_data(symbol, start_date, end_date, interval)
                data[symbol] = df
            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")
                
        return data
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """
        Get the latest price for a symbol.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Latest close price or None if unavailable
        """
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d")
            if not data.empty:
                return float(data['Close'].iloc[-1])
        except Exception as e:
            logger.error(f"Failed to get latest price for {symbol}: {e}")
        
        return None
    
    def get_price_at_datetime(
        self,
        symbol: str,
        dt: datetime,
        data: Optional[pd.DataFrame] = None
    ) -> Optional[float]:
        """
        Get the price at a specific datetime.
        
        Args:
            symbol: Stock ticker symbol
            dt: Target datetime
            data: Pre-loaded DataFrame (optional)
            
        Returns:
            Close price at the specified datetime
        """
        if data is None:
            # Fetch data around the target date
            start = (dt - timedelta(days=5)).strftime("%Y-%m-%d")
            end = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
            data = self.get_historical_data(symbol, start, end)
        
        if data.empty:
            return None
        
        # Find the closest timestamp
        try:
            # Try exact match first
            if dt in data.index:
                return float(data.loc[dt, 'Close'])
            
            # Find nearest timestamp
            idx = data.index.get_indexer([dt], method='ffill')[0]
            if idx >= 0:
                return float(data.iloc[idx]['Close'])
                
        except Exception as e:
            logger.error(f"Failed to get price at {dt} for {symbol}: {e}")
        
        return None
    
    def validate_symbol(self, symbol: str) -> bool:
        """
        Check if a symbol is valid.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            True if symbol is valid
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return 'symbol' in info or 'shortName' in info
        except:
            return False
    
    def clear_cache(self, symbol: Optional[str] = None):
        """
        Clear cached data.
        
        Args:
            symbol: Specific symbol to clear, or None to clear all
        """
        if symbol:
            # Clear specific symbol
            for file in os.listdir(self.cache_dir):
                if file.startswith(f"{symbol}_"):
                    os.remove(os.path.join(self.cache_dir, file))
                    logger.info(f"Cleared cache for {symbol}")
        else:
            # Clear all cache
            for file in os.listdir(self.cache_dir):
                os.remove(os.path.join(self.cache_dir, file))
            logger.info("Cleared all cache")
    
    def _get_cache_filename(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str
    ) -> str:
        """Generate cache filename."""
        filename = f"{symbol}_{start_date}_{end_date}_{interval}.csv"
        return os.path.join(self.cache_dir, filename)
