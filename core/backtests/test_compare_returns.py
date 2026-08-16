from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd

from core.backtests.compare_returns import (
    _select_requested_return,
    analyze_portfolio,
    compute_market_snapshot,
    compute_return,
    generate_markdown_report,
)


def _prices(days: int, start: float, end: float) -> pd.DataFrame:
    dates = [datetime(2025, 1, 1), datetime(2025, 1, 1) + timedelta(days=days)]
    return pd.DataFrame({"Close": [start, end], "Dividends": [0.0, 0.0]}, index=dates)


def test_partial_one_year_history_is_projected():
    stats = compute_return(_prices(182, 100.0, 110.0))
    requested_return, projected = _select_requested_return(stats, 365)
    assert projected is True
    assert requested_return == stats["annualized_return_pct"]
    assert 20.0 < requested_return < 22.0


def test_full_one_year_history_uses_observed_return():
    stats = compute_return(_prices(364, 100.0, 110.0))
    requested_return, projected = _select_requested_return(stats, 365)
    assert projected is False
    assert requested_return == stats["total_return_pct"]


def test_partial_non_one_year_request_is_not_projected():
    stats = compute_return(_prices(30, 100.0, 110.0))
    requested_return, projected = _select_requested_return(stats, 180)
    assert projected is False
    assert requested_return == stats["total_return_pct"]


def test_market_snapshot_computes_52_week_high_gap():
    dates = pd.to_datetime(["2025-01-02", "2025-06-03", "2025-12-31"])
    prices = pd.DataFrame(
        {"Close": [90.0, 110.0, 100.0], "High": [95.0, 120.0, 105.0]},
        index=dates,
    )

    snapshot = compute_market_snapshot(prices)

    assert snapshot["latest_price"] == 100.0
    assert snapshot["latest_price_date"] == "2025-12-31"
    assert snapshot["fifty_two_week_high"] == 120.0
    assert snapshot["fifty_two_week_high_date"] == "2025-06-03"
    assert abs(snapshot["from_fifty_two_week_high_pct"] - (-16.6667)) < 0.001


def test_market_snapshot_handles_missing_data():
    snapshot = compute_market_snapshot(None)
    assert snapshot["latest_price"] is None
    assert snapshot["from_fifty_two_week_high_pct"] is None


def test_portfolio_includes_benchmark_pe_metrics():
    holdings = pd.DataFrame({"Ticker": ["AAPL"], "MarketValue": [1000.0]})
    prices = _prices(364, 100.0, 110.0)
    benchmark_snapshot = {"forward_pe": 24.5, "trailing_pe": 26.0}
    holding_snapshot = {
        "latest_price": 110.0,
        "latest_price_date": "2026-01-01",
        "fifty_two_week_high": 120.0,
        "fifty_two_week_high_date": "2025-12-01",
        "from_fifty_two_week_high_pct": -8.3333,
        "forward_pe": 22.0,
        "trailing_pe": 25.0,
    }

    with (
        patch(
            "core.backtests.compare_returns.fetch_prices",
            side_effect=[prices, prices],
        ),
        patch(
            "core.backtests.compare_returns.fetch_market_snapshot",
            side_effect=[benchmark_snapshot, holding_snapshot],
        ),
    ):
        results = analyze_portfolio(
            holdings, "SPY", "2025-01-01", "2026-01-01"
        )

    assert results["benchmark_stats"]["forward_pe"] == 24.5
    assert results["benchmark_stats"]["trailing_pe"] == 26.0
    report = generate_markdown_report(results, "portfolio.csv")
    assert "| Benchmark Trailing P/E | 26.00 |" in report
    assert "| ForwardPE | TrailingPE |" in report
    assert "| -8.33% | 22.00 | 25.00 |" in report
