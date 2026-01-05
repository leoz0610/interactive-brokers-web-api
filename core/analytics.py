"""
Performance Analytics Module

Calculates performance metrics and statistics for backtests.
"""

import logging
from datetime import datetime
from typing import Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PerformanceAnalytics:
    """
    Calculates trading performance metrics.
    """

    def __init__(
        self, equity_history: List[Dict], transactions: List, initial_cash: float
    ):
        """
        Initialize PerformanceAnalytics.

        Args:
            equity_history: List of equity snapshots
            transactions: List of Transaction objects
            initial_cash: Initial capital
        """
        self.equity_history = equity_history
        self.transactions = transactions
        self.initial_cash = initial_cash

        # Convert to DataFrame for easier analysis
        if equity_history:
            self.equity_df = pd.DataFrame(equity_history)
            self.equity_df.set_index("timestamp", inplace=True)
        else:
            self.equity_df = pd.DataFrame()

    def calculate_metrics(self) -> Dict:
        """
        Calculate comprehensive performance metrics.

        Returns:
            Dictionary with performance metrics
        """
        if self.equity_df.empty:
            return self._empty_metrics()

        metrics = {}

        # Basic returns
        metrics["total_return"] = self._calculate_total_return()
        metrics["total_return_percent"] = self._calculate_total_return_percent()
        metrics["annualized_return"] = self._calculate_annualized_return()

        # Risk metrics
        metrics["volatility"] = self._calculate_volatility()
        metrics["sharpe_ratio"] = self._calculate_sharpe_ratio()
        metrics["max_drawdown"] = self._calculate_max_drawdown()
        metrics["max_drawdown_percent"] = self._calculate_max_drawdown_percent()

        # Trade statistics
        metrics["num_trades"] = len(self.transactions)
        metrics["num_winning_trades"] = self._count_winning_trades()
        metrics["num_losing_trades"] = self._count_losing_trades()
        metrics["win_rate"] = self._calculate_win_rate()
        metrics["avg_win"] = self._calculate_avg_win()
        metrics["avg_loss"] = self._calculate_avg_loss()
        metrics["profit_factor"] = self._calculate_profit_factor()
        metrics["largest_win"] = self._calculate_largest_win()
        metrics["largest_loss"] = self._calculate_largest_loss()

        # Time metrics
        metrics["trading_days"] = len(self.equity_df)
        metrics["start_date"] = str(self.equity_df.index[0])
        metrics["end_date"] = str(self.equity_df.index[-1])

        return metrics

    def _empty_metrics(self) -> Dict:
        """Return empty metrics when no data available."""
        return {
            "total_return": 0.0,
            "total_return_percent": 0.0,
            "annualized_return": 0.0,
            "volatility": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_percent": 0.0,
            "num_trades": 0,
            "num_winning_trades": 0,
            "num_losing_trades": 0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "largest_win": 0.0,
            "largest_loss": 0.0,
            "trading_days": 0,
            "start_date": None,
            "end_date": None,
        }

    def _calculate_total_return(self) -> float:
        """Calculate total return in dollars."""
        if self.equity_df.empty:
            return 0.0

        final_equity = self.equity_df["equity"].iloc[-1]
        return final_equity - self.initial_cash

    def _calculate_total_return_percent(self) -> float:
        """Calculate total return as percentage."""
        if self.initial_cash == 0:
            return 0.0

        return (self._calculate_total_return() / self.initial_cash) * 100

    def _calculate_annualized_return(self) -> float:
        """Calculate annualized return."""
        if self.equity_df.empty or len(self.equity_df) < 2:
            return 0.0

        # Calculate number of years
        start_date = self.equity_df.index[0]
        end_date = self.equity_df.index[-1]
        days = (end_date - start_date).days
        years = days / 365.25

        if years == 0:
            return 0.0

        # Calculate annualized return
        final_value = self.equity_df["equity"].iloc[-1]
        initial_value = self.initial_cash

        annualized = (pow(final_value / initial_value, 1 / years) - 1) * 100

        return annualized

    def _calculate_volatility(self) -> float:
        """Calculate annualized volatility."""
        if self.equity_df.empty or len(self.equity_df) < 2:
            return 0.0

        # Calculate daily returns
        returns = self.equity_df["equity"].pct_change().dropna()

        if len(returns) == 0:
            return 0.0

        # Annualized volatility (assuming 252 trading days)
        volatility = returns.std() * np.sqrt(252) * 100

        return volatility

    def _calculate_sharpe_ratio(self, risk_free_rate: float = 0.0) -> float:
        """
        Calculate Sharpe ratio.

        Args:
            risk_free_rate: Annual risk-free rate (default 0%)

        Returns:
            Sharpe ratio
        """
        if self.equity_df.empty or len(self.equity_df) < 2:
            return 0.0

        # Calculate daily returns
        returns = self.equity_df["equity"].pct_change().dropna()

        if len(returns) == 0 or returns.std() == 0:
            return 0.0

        # Annualized metrics
        annual_return = self._calculate_annualized_return() / 100
        annual_vol = self._calculate_volatility() / 100

        if annual_vol == 0:
            return 0.0

        sharpe = (annual_return - risk_free_rate) / annual_vol

        return sharpe

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown in dollars."""
        if self.equity_df.empty:
            return 0.0

        equity = self.equity_df["equity"]
        cummax = equity.cummax()
        drawdown = equity - cummax

        return abs(drawdown.min())

    def _calculate_max_drawdown_percent(self) -> float:
        """Calculate maximum drawdown as percentage."""
        if self.equity_df.empty:
            return 0.0

        equity = self.equity_df["equity"]
        cummax = equity.cummax()
        drawdown_pct = ((equity - cummax) / cummax) * 100

        return abs(drawdown_pct.min())

    def _count_winning_trades(self) -> int:
        """Count number of winning trades."""
        winning = 0

        # Group transactions by symbol and calculate P&L
        trades = self._calculate_trade_pnl()

        for pnl in trades:
            if pnl > 0:
                winning += 1

        return winning

    def _count_losing_trades(self) -> int:
        """Count number of losing trades."""
        losing = 0

        trades = self._calculate_trade_pnl()

        for pnl in trades:
            if pnl < 0:
                losing += 1

        return losing

    def _calculate_win_rate(self) -> float:
        """Calculate win rate percentage."""
        total_trades = len(self._calculate_trade_pnl())

        if total_trades == 0:
            return 0.0

        winning_trades = self._count_winning_trades()

        return (winning_trades / total_trades) * 100

    def _calculate_avg_win(self) -> float:
        """Calculate average winning trade."""
        trades = self._calculate_trade_pnl()
        winning_trades = [pnl for pnl in trades if pnl > 0]

        if not winning_trades:
            return 0.0

        return np.mean(winning_trades)

    def _calculate_avg_loss(self) -> float:
        """Calculate average losing trade."""
        trades = self._calculate_trade_pnl()
        losing_trades = [pnl for pnl in trades if pnl < 0]

        if not losing_trades:
            return 0.0

        return np.mean(losing_trades)

    def _calculate_profit_factor(self) -> float:
        """Calculate profit factor (gross profit / gross loss)."""
        trades = self._calculate_trade_pnl()

        gross_profit = sum(pnl for pnl in trades if pnl > 0)
        gross_loss = abs(sum(pnl for pnl in trades if pnl < 0))

        if gross_loss == 0:
            return 0.0 if gross_profit == 0 else float("inf")

        return gross_profit / gross_loss

    def _calculate_largest_win(self) -> float:
        """Calculate largest winning trade."""
        trades = self._calculate_trade_pnl()
        winning_trades = [pnl for pnl in trades if pnl > 0]

        if not winning_trades:
            return 0.0

        return max(winning_trades)

    def _calculate_largest_loss(self) -> float:
        """Calculate largest losing trade."""
        trades = self._calculate_trade_pnl()
        losing_trades = [pnl for pnl in trades if pnl < 0]

        if not losing_trades:
            return 0.0

        return min(losing_trades)

    def _calculate_trade_pnl(self) -> List[float]:
        """
        Calculate P&L for each completed round-trip trade.

        Returns:
            List of P&L values for each trade
        """
        from .order_manager import OrderSide

        trade_pnls = []

        # Group by symbol
        symbol_txns = {}
        for txn in self.transactions:
            if txn.symbol not in symbol_txns:
                symbol_txns[txn.symbol] = []
            symbol_txns[txn.symbol].append(txn)

        # Calculate P&L for each symbol using FIFO
        for symbol, txns in symbol_txns.items():
            buy_queue = []

            for txn in txns:
                if txn.side == OrderSide.BUY:
                    buy_queue.append(txn)
                else:
                    # Match with buys
                    remaining = txn.quantity

                    while remaining > 0 and buy_queue:
                        buy_txn = buy_queue[0]

                        if buy_txn.quantity <= remaining:
                            # Fully close this buy
                            pnl = (
                                buy_txn.quantity * (txn.price - buy_txn.price)
                                - buy_txn.commission
                                - txn.commission
                            )
                            trade_pnls.append(pnl)
                            remaining -= buy_txn.quantity
                            buy_queue.pop(0)
                        else:
                            # Partially close this buy
                            pnl = (
                                remaining * (txn.price - buy_txn.price) - txn.commission
                            )
                            trade_pnls.append(pnl)
                            buy_txn.quantity -= remaining
                            remaining = 0

        return trade_pnls
