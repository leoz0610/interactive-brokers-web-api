"""
Utility Helper Functions

Common utility functions for the simulation package.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any
import pandas as pd


def save_results_to_json(results: Dict, filename: str):
    """
    Save backtest results to JSON file.
    
    Args:
        results: Results dictionary
        filename: Output filename
    """
    # Convert non-serializable objects
    serializable_results = _make_serializable(results)
    
    with open(filename, 'w') as f:
        json.dump(serializable_results, f, indent=2)


def load_results_from_json(filename: str) -> Dict:
    """
    Load backtest results from JSON file.
    
    Args:
        filename: Input filename
        
    Returns:
        Results dictionary
    """
    with open(filename, 'r') as f:
        return json.load(f)


def _make_serializable(obj: Any) -> Any:
    """
    Convert object to JSON-serializable format.
    
    Args:
        obj: Object to convert
        
    Returns:
        Serializable version of object
    """
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_make_serializable(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif pd.isna(obj):
        return None
    elif isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    else:
        return str(obj)


def format_currency(value: float) -> str:
    """
    Format value as currency.
    
    Args:
        value: Numeric value
        
    Returns:
        Formatted string
    """
    return f"${value:,.2f}"


def format_percent(value: float) -> str:
    """
    Format value as percentage.
    
    Args:
        value: Numeric value
        
    Returns:
        Formatted string
    """
    return f"{value:+.2f}%"


def calculate_date_range(end_date: str, days: int) -> str:
    """
    Calculate start date given end date and number of days.
    
    Args:
        end_date: End date in YYYY-MM-DD format
        days: Number of days to go back
        
    Returns:
        Start date in YYYY-MM-DD format
    """
    end = datetime.strptime(end_date, "%Y-%m-%d")
    start = end - timedelta(days=days)
    return start.strftime("%Y-%m-%d")


def print_results_summary(results: Dict):
    """
    Print a formatted summary of backtest results.
    
    Args:
        results: Results dictionary
    """
    print("\n" + "="*60)
    print(f"BACKTEST RESULTS: {results['strategy']}")
    print("="*60)
    
    print(f"\nPeriod: {results['start_date']} to {results['end_date']}")
    print(f"Symbols: {', '.join(results['symbols'])}")
    
    portfolio = results['portfolio_summary']
    print(f"\n{'PORTFOLIO SUMMARY':-^60}")
    print(f"Initial Capital:    {format_currency(portfolio['initial_cash'])}")
    print(f"Final Value:        {format_currency(portfolio['total_value'])}")
    print(f"Cash:               {format_currency(portfolio['cash'])}")
    print(f"Positions Value:    {format_currency(portfolio['positions_value'])}")
    print(f"Total P&L:          {format_currency(portfolio['total_pnl'])} ({format_percent(portfolio['total_pnl_percent'])})")
    print(f"Realized P&L:       {format_currency(portfolio['realized_pnl'])}")
    print(f"Unrealized P&L:     {format_currency(portfolio['unrealized_pnl'])}")
    
    metrics = results['performance_metrics']
    print(f"\n{'PERFORMANCE METRICS':-^60}")
    print(f"Total Return:       {format_percent(metrics['total_return_percent'])}")
    print(f"Annualized Return:  {format_percent(metrics['annualized_return'])}")
    print(f"Volatility:         {format_percent(metrics['volatility'])}")
    print(f"Sharpe Ratio:       {metrics['sharpe_ratio']:.2f}")
    print(f"Max Drawdown:       {format_currency(metrics['max_drawdown'])} ({format_percent(metrics['max_drawdown_percent'])})")
    
    print(f"\n{'TRADE STATISTICS':-^60}")
    print(f"Total Trades:       {metrics['num_trades']}")
    print(f"Winning Trades:     {metrics['num_winning_trades']}")
    print(f"Losing Trades:      {metrics['num_losing_trades']}")
    print(f"Win Rate:           {format_percent(metrics['win_rate'])}")
    print(f"Avg Win:            {format_currency(metrics['avg_win'])}")
    print(f"Avg Loss:           {format_currency(metrics['avg_loss'])}")
    print(f"Profit Factor:      {metrics['profit_factor']:.2f}")
    print(f"Largest Win:        {format_currency(metrics['largest_win'])}")
    print(f"Largest Loss:       {format_currency(metrics['largest_loss'])}")
    
    print("\n" + "="*60 + "\n")


def validate_date_format(date_str: str) -> bool:
    """
    Validate date string format.
    
    Args:
        date_str: Date string to validate
        
    Returns:
        True if valid YYYY-MM-DD format
    """
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False
