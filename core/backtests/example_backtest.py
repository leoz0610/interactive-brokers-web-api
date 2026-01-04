#!/usr/bin/env python3
"""
Example Backtest Script

Demonstrates how to use the core framework to backtest trading strategies.
"""

import os
import sys

# Add project root to path
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, project_root)

from core import BacktestEngine
from core.strategies import BuyAndHoldStrategy, MovingAverageCrossoverStrategy
from core.utils import print_results_summary, save_results_to_json


def run_buy_and_hold_example():
    """
    Run a simple buy and hold backtest.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Buy and Hold Strategy")
    print("=" * 60)

    # Initialize backtest engine
    engine = BacktestEngine(
        initial_cash=100000.0,
        commission_per_share=0.0,
        commission_percent=0.1,  # 0.1% commission
        slippage_percent=0.05,  # 0.05% slippage
    )

    # Create strategy
    strategy = BuyAndHoldStrategy(allocation_per_symbol=0.9)
    engine.set_strategy(strategy)

    # Load data
    symbols = ["AAPL", "MSFT", "GOOGL"]
    start_date = "2023-01-01"
    end_date = "2024-01-01"

    print(f"\nLoading data for {symbols}...")
    engine.load_data(symbols, start_date, end_date)

    # Run backtest
    print("Running backtest...")
    results = engine.run()

    # Print results
    print_results_summary(results)

    # Save results
    output_file = "core/simulation/data/buy_and_hold_results.json"
    save_results_to_json(results, output_file)
    print(f"Results saved to {output_file}")

    return results


def run_moving_average_example():
    """
    Run a moving average crossover backtest.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Moving Average Crossover Strategy")
    print("=" * 60)

    # Initialize backtest engine
    engine = BacktestEngine(
        initial_cash=100000.0,
        commission_per_share=0.0,
        commission_percent=0.1,
        slippage_percent=0.05,
    )

    # Create strategy
    strategy = MovingAverageCrossoverStrategy(
        fast_period=20, slow_period=50, position_size_pct=30.0
    )
    engine.set_strategy(strategy)

    # Load data
    symbols = ["SPY", "QQQ"]
    start_date = "2022-01-01"
    end_date = "2024-01-01"

    print(f"\nLoading data for {symbols}...")
    engine.load_data(symbols, start_date, end_date)

    # Run backtest
    print("Running backtest...")
    results = engine.run()

    # Print results
    print_results_summary(results)

    # Save results
    output_file = "core/simulation/data/moving_average_results.json"
    save_results_to_json(results, output_file)
    print(f"Results saved to {output_file}")

    return results


def compare_strategies():
    """
    Compare multiple strategies.
    """
    print("\n" + "=" * 60)
    print("STRATEGY COMPARISON")
    print("=" * 60)

    symbols = ["SPY"]
    start_date = "2023-01-01"
    end_date = "2024-01-01"

    strategies = [
        BuyAndHoldStrategy(),
        MovingAverageCrossoverStrategy(fast_period=10, slow_period=30),
        MovingAverageCrossoverStrategy(fast_period=20, slow_period=50),
    ]

    results_list = []

    for strategy in strategies:
        print(f"\nTesting: {strategy.name}")

        engine = BacktestEngine(
            initial_cash=100000.0, commission_percent=0.1, slippage_percent=0.05
        )

        engine.set_strategy(strategy)
        engine.load_data(symbols, start_date, end_date)
        results = engine.run()
        results_list.append(results)

    # Print comparison
    print("\n" + "=" * 60)
    print("COMPARISON SUMMARY")
    print("=" * 60)
    print(f"\n{'Strategy':<40} {'Return':<15} {'Sharpe':<10} {'Max DD':<10}")
    print("-" * 75)

    for results in results_list:
        strategy_name = results["strategy"]
        total_return = results["performance_metrics"]["total_return_percent"]
        sharpe = results["performance_metrics"]["sharpe_ratio"]
        max_dd = results["performance_metrics"]["max_drawdown_percent"]

        print(
            f"{strategy_name:<40} {total_return:>+6.2f}%        {sharpe:>6.2f}    {max_dd:>6.2f}%"
        )

    print()


if __name__ == "__main__":
    # Run examples
    try:
        # Example 1: Buy and Hold
        run_buy_and_hold_example()

        # Example 2: Moving Average Crossover
        run_moving_average_example()

        # Example 3: Strategy Comparison
        compare_strategies()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback

        traceback.print_exc()
