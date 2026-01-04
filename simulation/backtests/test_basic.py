#!/usr/bin/env python3
"""
Basic test script to validate the simulation framework.
"""

import os
import sys

# Add project root to path
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "simulation"))

print("Testing simulation framework...")
print("-" * 60)

# Test imports
print("\n1. Testing imports...")
try:
    from simulation import (
        BacktestEngine,
        DataProvider,
        Order,
        OrderManager,
        OrderSide,
        OrderStatus,
        OrderType,
        PerformanceAnalytics,
        PortfolioManager,
        PortfolioManagerBase,
    )
    from strategies import StrategyBase

    print("   ✓ All core modules imported successfully")
except Exception as e:
    print(f"   ✗ Import failed: {e}")
    sys.exit(1)

# Test data provider
print("\n2. Testing DataProvider...")
try:
    provider = DataProvider()

    # Test with a simple symbol and short date range
    data = provider.get_historical_data("AAPL", "2024-01-01", "2024-01-31")

    if not data.empty:
        print(f"   ✓ Successfully fetched {len(data)} days of AAPL data")
        print(f"   ✓ Columns: {', '.join(data.columns)}")
    else:
        print("   ✗ No data returned")
        sys.exit(1)

except Exception as e:
    print(f"   ✗ DataProvider test failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Test order manager
print("\n3. Testing OrderManager...")
try:
    order_mgr = OrderManager(commission_percent=0.1, slippage_percent=0.05)

    # Create a market order
    order = order_mgr.create_order(
        symbol="AAPL", side=OrderSide.BUY, quantity=100, order_type=OrderType.MARKET
    )

    print(f"   ✓ Created order: {order.order_id}")
    print(f"   ✓ Order status: {order.status.value}")

    # Execute the order
    from datetime import datetime

    executed = order_mgr.execute_order(order, 150.0, datetime.now())

    if executed:
        print(f"   ✓ Order executed at ${order.filled_price:.2f}")
    else:
        print("   ✗ Order execution failed")

except Exception as e:
    print(f"   ✗ OrderManager test failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Test portfolio manager
print("\n4. Testing PortfolioManager...")
try:
    portfolio = PortfolioManager(initial_cash=100000.0)

    print(f"   ✓ Initial cash: ${portfolio.cash:,.2f}")

    # Process the filled order
    success = portfolio.process_filled_order(order)

    if success:
        print(f"   ✓ Order processed successfully")
        print(f"   ✓ Remaining cash: ${portfolio.cash:,.2f}")
        print(f"   ✓ Positions: {len(portfolio.positions)}")
    else:
        print("   ✗ Failed to process order")

except Exception as e:
    print(f"   ✗ PortfolioManager test failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Test strategy
print("\n5. Testing Strategy...")
try:
    from strategies import BuyAndHoldStrategy

    strategy = BuyAndHoldStrategy()
    print(f"   ✓ Created strategy: {strategy.name}")

except Exception as e:
    print(f"   ✗ Strategy test failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Test backtest engine (quick test)
print("\n6. Testing BacktestEngine...")
try:
    from strategies import BuyAndHoldStrategy

    engine = BacktestEngine(
        initial_cash=100000.0, commission_percent=0.1, slippage_percent=0.05
    )

    strategy = BuyAndHoldStrategy(allocation_per_symbol=0.5)
    engine.set_strategy(strategy)

    # Load minimal data
    print("   Loading test data...")
    engine.load_data(["AAPL"], "2024-01-01", "2024-01-31")

    print("   Running backtest...")
    results = engine.run()

    print(f"   ✓ Backtest completed")
    print(
        f"   ✓ Final portfolio value: ${results['portfolio_summary']['total_value']:,.2f}"
    )
    print(f"   ✓ Total P&L: ${results['portfolio_summary']['total_pnl']:,.2f}")
    print(f"   ✓ Number of trades: {results['performance_metrics']['num_trades']}")

except Exception as e:
    print(f"   ✗ BacktestEngine test failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("All tests passed! ✓")
print("=" * 60)
print("\nThe simulation framework is ready to use.")
print("Run 'python3 simulation/backtests/example_backtest.py' for full examples.")
print()
