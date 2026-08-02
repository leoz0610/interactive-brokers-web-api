from datetime import datetime, timedelta

import pandas as pd

from core.backtests.compare_returns import _select_requested_return, compute_return


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
