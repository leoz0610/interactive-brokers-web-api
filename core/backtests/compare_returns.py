#!/usr/bin/env python3
"""
Portfolio Return Comparison Tool

Reads a spreadsheet (CSV or Excel) of stock holdings, fetches historical
price data via yfinance, computes return performance over a configurable
period, compares each holding against a benchmark index, and produces a
markdown report.

Usage examples:

    # From ticker list (original mode)
    python compare_returns.py AAPL MSFT GOOGL --start 2023-01-01 --end 2024-01-01

    # From spreadsheet with markdown report
    python compare_returns.py --input portfolio.csv --output report.md

    # Custom benchmark and period
    python compare_returns.py --input portfolio.xlsx --benchmark VOO --period 6m
"""

import argparse
import logging
import math
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Auto-activate the project venv if dependencies aren't available
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_venv_site = os.path.join(project_root, "core", "venv", "lib")
if os.path.isdir(_venv_site):
    import glob as _gl

    _sp = _gl.glob(os.path.join(_venv_site, "python*", "site-packages"))
    for _p in _sp:
        if _p not in sys.path:
            sys.path.insert(0, _p)

import pandas as pd  # noqa: E402
import yfinance as yf  # noqa: E402

# Add project root to path for core.utils
sys.path.insert(0, project_root)

from core.utils import save_results_to_json  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

DEFAULT_BENCHMARK = "SPY"
DEFAULT_PERIOD = "1y"
TOP_N = 5

# Accepted column-name variations (all compared lowercase / stripped)
COLUMN_ALIASES = {
    "Ticker": ["ticker", "symbol", "stock", "stock_ticker"],
    "MarketValue": [
        "marketvalue",
        "market_value",
        "market value",
        "currentvalue",
        "current_value",
        "current value",
        "value",
    ],
    "Portfolio": ["portfolio", "account", "portfolio_name"],
    "Shares": ["shares", "quantity", "qty"],
    "CostBasis": [
        "costbasis",
        "cost_basis",
        "cost basis",
        "cost",
        "avgcost",
        "avg_cost",
    ],
}

PERIOD_UNITS = {"d": 1, "w": 7, "m": 30, "y": 365}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_period(period_str: str) -> int:
    """Convert a period string like '1y', '6m', '90d' to calendar days."""
    period_str = period_str.strip().lower()
    if not period_str:
        raise ValueError("Empty period string")
    unit = period_str[-1]
    if unit not in PERIOD_UNITS:
        raise ValueError(
            f"Unknown period unit '{unit}'. Use one of: {list(PERIOD_UNITS)}"
        )
    try:
        count = int(period_str[:-1])
    except ValueError:
        raise ValueError(f"Invalid period number in '{period_str}'")
    return count * PERIOD_UNITS[unit]


def resolve_dates(
    start: Optional[str], end: Optional[str], period: str
) -> Tuple[str, str]:
    """Determine start/end dates from explicit values or period string."""
    if end:
        end_dt = datetime.strptime(end, "%Y-%m-%d")
    else:
        end_dt = datetime.today()

    if start:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
    else:
        days = parse_period(period)
        start_dt = end_dt - timedelta(days=days)

    return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")


def fmt_pct(value: Optional[float]) -> str:
    """Format a number as a percentage string."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    return f"{value:+.2f}%"


def fmt_dollar(value: Optional[float]) -> str:
    """Format a number as a dollar string."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    return f"${value:,.2f}"


# ---------------------------------------------------------------------------
# Spreadsheet loading
# ---------------------------------------------------------------------------


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename spreadsheet columns to canonical names using COLUMN_ALIASES."""
    col_map = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for col in df.columns:
            if col.strip().lower() in aliases:
                col_map[col] = canonical
                break
    return df.rename(columns=col_map)


def load_holdings(filepath: str) -> pd.DataFrame:
    """
    Load holdings from a CSV or Excel file.

    Returns a DataFrame with at least 'Ticker' and 'MarketValue' columns.
    Rows with missing tickers or non-numeric market values are dropped.
    Duplicate tickers are aggregated (market values summed).
    """
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(filepath, engine="openpyxl")
    elif ext == ".csv":
        df = pd.read_csv(filepath)
    else:
        raise ValueError(f"Unsupported file format: {ext}")

    df = _normalize_columns(df)

    if "Ticker" not in df.columns:
        raise ValueError(
            "Spreadsheet must contain a 'Ticker' column " f"(found: {list(df.columns)})"
        )

    # Clean up
    df = df.dropna(subset=["Ticker"])
    df["Ticker"] = df["Ticker"].astype(str).str.strip().str.upper()
    df = df[df["Ticker"] != ""]

    # Ensure MarketValue is numeric; fill missing with 0
    if "MarketValue" in df.columns:
        df["MarketValue"] = pd.to_numeric(df["MarketValue"], errors="coerce").fillna(0)
    else:
        df["MarketValue"] = 0.0

    # Aggregate duplicates
    agg_cols = {"MarketValue": "sum"}
    for col in ("Shares", "CostBasis"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            agg_cols[col] = "sum"
    # Keep first Portfolio label if present
    if "Portfolio" in df.columns:
        agg_cols["Portfolio"] = "first"

    df = df.groupby("Ticker", as_index=False).agg(agg_cols)

    return df


# ---------------------------------------------------------------------------
# Price fetching and return calculation
# ---------------------------------------------------------------------------


def _yf_ticker(ticker: str) -> str:
    """Normalize a ticker symbol for Yahoo Finance.

    Many brokerages use a dot for share classes (e.g. BRK.B) while Yahoo
    Finance expects a hyphen (BRK-B).
    """
    return ticker.replace(".", "-")


def fetch_prices(ticker: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """Fetch adjusted-close price history from yfinance. Returns None on failure."""
    try:
        t = yf.Ticker(_yf_ticker(ticker))
        df = t.history(start=start_date, end=end_date, auto_adjust=True)
        if df.empty:
            return None
        return df
    except Exception as e:
        logger.warning(f"Failed to fetch data for {ticker}: {e}")
        return None


def compute_return(df: pd.DataFrame) -> dict:
    """
    Compute return statistics from a price DataFrame.

    Returns dict with keys: total_return_pct, price_return_pct,
    dividend_return_pct, annualized_return_pct, max_drawdown_pct,
    volatility_pct, start_price, end_price, start_date, end_date.

    Note: Since prices are fetched with auto_adjust=True, the Close
    column reflects adjusted prices (split- and dividend-adjusted).
    Total return is computed from these adjusted prices.  Dividend
    return is derived from the Dividends column (sum of dividends
    paid divided by the starting adjusted price).  Price return is
    the remainder: total_return - dividend_return.
    """
    if df is None or df.empty or len(df) < 2:
        return {
            "total_return_pct": None,
            "price_return_pct": None,
            "dividend_return_pct": None,
            "annualized_return_pct": None,
            "max_drawdown_pct": None,
            "volatility_pct": None,
            "start_price": None,
            "end_price": None,
            "start_date": None,
            "end_date": None,
        }

    close = df["Close"]
    start_price = float(close.iloc[0])
    end_price = float(close.iloc[-1])
    total_return_pct = ((end_price / start_price) - 1) * 100

    # Dividend return: sum of dividends paid over the period divided
    # by the starting adjusted price.  Price return is the remainder.
    dividend_return_pct = 0.0
    if "Dividends" in df.columns and start_price > 0:
        total_dividends = float(df["Dividends"].sum())
        dividend_return_pct = (total_dividends / start_price) * 100
    price_return_pct = total_return_pct - dividend_return_pct

    start_dt = df.index[0]
    end_dt = df.index[-1]
    days = (end_dt - start_dt).days
    years = days / 365.25
    if years > 0 and start_price > 0:
        annualized_return_pct = (pow(end_price / start_price, 1 / years) - 1) * 100
    else:
        annualized_return_pct = 0.0

    cummax = close.cummax()
    drawdown_pct = ((close - cummax) / cummax) * 100
    max_drawdown_pct = abs(float(drawdown_pct.min()))

    daily_returns = close.pct_change().dropna()
    if len(daily_returns) > 0:
        volatility_pct = float(daily_returns.std() * (252**0.5) * 100)
    else:
        volatility_pct = 0.0

    return {
        "total_return_pct": total_return_pct,
        "price_return_pct": price_return_pct,
        "dividend_return_pct": dividend_return_pct,
        "annualized_return_pct": annualized_return_pct,
        "max_drawdown_pct": max_drawdown_pct,
        "volatility_pct": volatility_pct,
        "start_price": start_price,
        "end_price": end_price,
        "start_date": str(start_dt.date()),
        "end_date": str(end_dt.date()),
    }


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------


def analyze_portfolio(
    holdings: pd.DataFrame,
    benchmark_ticker: str,
    start_date: str,
    end_date: str,
) -> dict:
    """
    Run the full portfolio analysis.

    Args:
        holdings: DataFrame with Ticker, MarketValue, and optional columns.
        benchmark_ticker: Benchmark ticker symbol.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).

    Returns:
        Results dict with all data needed to render the report.
    """
    # -- Benchmark --
    logger.info(f"Fetching benchmark {benchmark_ticker}...")
    bench_df = fetch_prices(benchmark_ticker, start_date, end_date)
    bench_stats = compute_return(bench_df)
    bench_return = bench_stats["total_return_pct"]

    # -- Holdings --
    total_mv = holdings["MarketValue"].sum()
    holding_results = []
    data_issues = []

    tickers = holdings["Ticker"].tolist()
    logger.info(f"Fetching data for {len(tickers)} holdings...")

    for _, row in holdings.iterrows():
        ticker = row["Ticker"]
        market_value = row["MarketValue"]
        weight = (market_value / total_mv * 100) if total_mv > 0 else 0.0

        price_df = fetch_prices(ticker, start_date, end_date)
        stats = compute_return(price_df)

        status = "OK"
        notes = ""

        if stats["total_return_pct"] is None:
            status = "ERROR"
            notes = "No price data available"
            data_issues.append({"ticker": ticker, "reason": notes})
        elif price_df is not None:
            actual_days = (price_df.index[-1] - price_df.index[0]).days
            requested_days = (
                datetime.strptime(end_date, "%Y-%m-%d")
                - datetime.strptime(start_date, "%Y-%m-%d")
            ).days
            if actual_days < requested_days * 0.8:
                status = "PARTIAL"
                notes = f"Only {actual_days}d of data (requested ~{requested_days}d)"
                data_issues.append({"ticker": ticker, "reason": notes})

        excess = None
        if stats["total_return_pct"] is not None and bench_return is not None:
            excess = stats["total_return_pct"] - bench_return

        holding_results.append(
            {
                "ticker": ticker,
                "market_value": market_value,
                "weight": weight,
                "start_date": stats["start_date"],
                "end_date": stats["end_date"],
                "start_price": stats["start_price"],
                "end_price": stats["end_price"],
                "return_pct": stats["total_return_pct"],
                "price_return_pct": stats["price_return_pct"],
                "dividend_return_pct": stats["dividend_return_pct"],
                "annualized_return_pct": stats["annualized_return_pct"],
                "volatility_pct": stats["volatility_pct"],
                "max_drawdown_pct": stats["max_drawdown_pct"],
                "benchmark_return_pct": bench_return,
                "excess_return_pct": excess,
                "status": status,
                "notes": notes,
            }
        )

    # Sort by market value descending
    holding_results.sort(key=lambda h: h["market_value"], reverse=True)

    # Portfolio-level weighted return
    portfolio_weighted_return = 0.0
    portfolio_weighted_excess = 0.0
    valid_weight_sum = 0.0
    for h in holding_results:
        if h["return_pct"] is not None:
            w = h["weight"] / 100
            portfolio_weighted_return += w * h["return_pct"]
            valid_weight_sum += w
            if h["excess_return_pct"] is not None:
                portfolio_weighted_excess += w * h["excess_return_pct"]

    return {
        "analysis_date": datetime.today().strftime("%Y-%m-%d"),
        "start_date": start_date,
        "end_date": end_date,
        "benchmark_ticker": benchmark_ticker,
        "benchmark_stats": bench_stats,
        "total_market_value": total_mv,
        "num_holdings": len(holdings),
        "num_valid": sum(1 for h in holding_results if h["status"] != "ERROR"),
        "portfolio_weighted_return_pct": portfolio_weighted_return,
        "portfolio_weighted_excess_pct": portfolio_weighted_excess,
        "holdings": holding_results,
        "data_issues": data_issues,
    }


# ---------------------------------------------------------------------------
# Ticker-list mode (original compare_returns behaviour)
# ---------------------------------------------------------------------------


def compare_tickers(
    tickers: List[str],
    benchmarks: List[str],
    start_date: str,
    end_date: str,
) -> dict:
    """
    Lightweight comparison: fetch data and compute returns for tickers and
    benchmarks. Returns a dict with 'tickers' and 'benchmarks' keys.
    """
    all_symbols = list(dict.fromkeys(tickers + benchmarks))
    data = {}
    for sym in all_symbols:
        df = fetch_prices(sym, start_date, end_date)
        if df is not None:
            data[sym] = df

    ticker_results = {}
    for sym in tickers:
        if sym in data:
            ticker_results[sym] = compute_return(data[sym])
        else:
            ticker_results[sym] = {"error": "no data"}

    benchmark_results = {}
    for sym in benchmarks:
        if sym in data:
            benchmark_results[sym] = compute_return(data[sym])
        else:
            benchmark_results[sym] = {"error": "no data"}

    return {
        "start_date": start_date,
        "end_date": end_date,
        "tickers": ticker_results,
        "benchmarks": benchmark_results,
    }


def print_comparison(results: dict) -> None:
    """Print a formatted comparison table (ticker-list mode)."""
    print(f"\nPeriod: {results['start_date']} to {results['end_date']}")

    header = (
        f"{'Symbol':<10} {'Type':<12} {'Start':>10} {'End':>10} "
        f"{'TotalRet':>10} {'PriceRet':>10} {'DivRet':>10} "
        f"{'Annual':>10} {'Vol':>10} {'Max DD':>10}"
    )
    print("\n" + header)
    print("-" * len(header))

    def _row(symbol: str, label: str, stats: dict) -> None:
        if "error" in stats:
            print(f"{symbol:<10} {label:<12} {'N/A — ' + stats['error']:>10}")
            return
        print(
            f"{symbol:<10} {label:<12} "
            f"{fmt_dollar(stats['start_price']):>10} "
            f"{fmt_dollar(stats['end_price']):>10} "
            f"{fmt_pct(stats['total_return_pct']):>10} "
            f"{fmt_pct(stats['price_return_pct']):>10} "
            f"{fmt_pct(stats['dividend_return_pct']):>10} "
            f"{fmt_pct(stats['annualized_return_pct']):>10} "
            f"{fmt_pct(stats['volatility_pct']):>10} "
            f"{fmt_pct(stats['max_drawdown_pct']):>10}"
        )

    for sym, stats in results["benchmarks"].items():
        _row(sym, "Benchmark", stats)
    print("-" * len(header))
    for sym, stats in results["tickers"].items():
        _row(sym, "Ticker", stats)
    print()


# ---------------------------------------------------------------------------
# Markdown report generation
# ---------------------------------------------------------------------------


def generate_markdown_report(results: dict, input_file: str, top_n: int = TOP_N) -> str:
    """Build the full markdown report string from analysis results."""
    lines = []

    def ln(text: str = "") -> None:
        lines.append(text)

    bench = results["benchmark_stats"]
    bench_ret = bench["total_return_pct"]
    holdings = results["holdings"]
    valid_holdings = [h for h in holdings if h["status"] != "ERROR"]

    # ---- Title ----
    ln("# Portfolio Performance Report")
    ln()

    # ---- 1. Overview ----
    ln("## 1. Overview")
    ln()
    ln(f"| Metric | Value |")
    ln(f"|---|---|")
    ln(f"| Analysis Date | {results['analysis_date']} |")
    ln(f"| Input File | `{os.path.basename(input_file)}` |")
    ln(f"| Benchmark | {results['benchmark_ticker']} |")
    ln(f"| Period | {results['start_date']} to {results['end_date']} |")
    ln(f"| Holdings Analyzed | {results['num_valid']} of {results['num_holdings']} |")
    ln(f"| Total Market Value | {fmt_dollar(results['total_market_value'])} |")
    ln(f"| Benchmark Return | {fmt_pct(bench_ret)} |")
    ln(
        f"| Portfolio Weighted Return | {fmt_pct(results['portfolio_weighted_return_pct'])} |"
    )
    ln(
        f"| Portfolio Excess vs Benchmark | {fmt_pct(results['portfolio_weighted_excess_pct'])} |"
    )
    ln()

    # ---- 2. Holdings Summary Table ----
    ln("## 2. Holdings Summary")
    ln()
    ln(
        "| Ticker | MarketValue | Weight | StartDate | EndDate | StartPrice "
        "| EndPrice | TotalReturn | PriceReturn | DividendReturn "
        "| BenchmarkReturn | ExcessVsBenchmark | Status |"
    )
    ln("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for h in holdings:
        ln(
            f"| {h['ticker']} "
            f"| {fmt_dollar(h['market_value'])} "
            f"| {fmt_pct(h['weight'])} "
            f"| {h['start_date'] or 'N/A'} "
            f"| {h['end_date'] or 'N/A'} "
            f"| {fmt_dollar(h['start_price'])} "
            f"| {fmt_dollar(h['end_price'])} "
            f"| {fmt_pct(h['return_pct'])} "
            f"| {fmt_pct(h['price_return_pct'])} "
            f"| {fmt_pct(h['dividend_return_pct'])} "
            f"| {fmt_pct(h['benchmark_return_pct'])} "
            f"| {fmt_pct(h['excess_return_pct'])} "
            f"| {h['status']} |"
        )
    ln()

    # ---- 3. Top Outperformers ----
    ranked = [h for h in valid_holdings if h["excess_return_pct"] is not None]
    ranked_by_excess = sorted(
        ranked, key=lambda h: h["excess_return_pct"], reverse=True
    )

    ln("## 3. Top Outperformers")
    ln()
    top = ranked_by_excess[:top_n]
    if top:
        ln(
            "| Rank | Ticker | TotalReturn | PriceReturn | DividendReturn | Excess vs Benchmark |"
        )
        ln("|---|---|---|---|---|---|")
        for i, h in enumerate(top, 1):
            ln(
                f"| {i} | {h['ticker']} | {fmt_pct(h['return_pct'])} "
                f"| {fmt_pct(h['price_return_pct'])} | {fmt_pct(h['dividend_return_pct'])} "
                f"| {fmt_pct(h['excess_return_pct'])} |"
            )
    else:
        ln("No valid holdings to rank.")
    ln()

    # ---- 4. Top Underperformers ----
    ln("## 4. Top Underperformers")
    ln()
    bottom = (
        ranked_by_excess[-top_n:] if len(ranked_by_excess) > top_n else ranked_by_excess
    )
    bottom = sorted(bottom, key=lambda h: h["excess_return_pct"])
    if bottom:
        ln(
            "| Rank | Ticker | TotalReturn | PriceReturn | DividendReturn | Excess vs Benchmark |"
        )
        ln("|---|---|---|---|---|---|")
        for i, h in enumerate(bottom, 1):
            ln(
                f"| {i} | {h['ticker']} | {fmt_pct(h['return_pct'])} "
                f"| {fmt_pct(h['price_return_pct'])} | {fmt_pct(h['dividend_return_pct'])} "
                f"| {fmt_pct(h['excess_return_pct'])} |"
            )
    else:
        ln("No valid holdings to rank.")
    ln()

    # ---- 5. Portfolio Insights ----
    ln("## 5. Portfolio Insights")
    ln()
    insights = _generate_insights(results, ranked_by_excess)
    for paragraph in insights:
        ln(paragraph)
        ln()

    # ---- 6. Data Issues ----
    ln("## 6. Data Issues")
    ln()
    if results["data_issues"]:
        ln("| Ticker | Issue |")
        ln("|---|---|")
        for issue in results["data_issues"]:
            ln(f"| {issue['ticker']} | {issue['reason']} |")
    else:
        ln("No data issues detected.")
    ln()

    return "\n".join(lines)


def _generate_insights(results: dict, ranked: List[dict]) -> List[str]:
    """Produce narrative insight paragraphs."""
    paragraphs = []
    holdings = results["holdings"]
    valid = [h for h in holdings if h["status"] != "ERROR"]
    bench_ret = results["benchmark_stats"]["total_return_pct"]
    pw_ret = results["portfolio_weighted_return_pct"]
    pw_excess = results["portfolio_weighted_excess_pct"]

    # Beat or trail benchmark
    if bench_ret is not None:
        if pw_excess > 0:
            paragraphs.append(
                f"The portfolio's weighted return of {fmt_pct(pw_ret)} **outperformed** "
                f"the {results['benchmark_ticker']} benchmark ({fmt_pct(bench_ret)}) "
                f"by {fmt_pct(pw_excess)}."
            )
        elif pw_excess < 0:
            paragraphs.append(
                f"The portfolio's weighted return of {fmt_pct(pw_ret)} **trailed** "
                f"the {results['benchmark_ticker']} benchmark ({fmt_pct(bench_ret)}) "
                f"by {fmt_pct(abs(pw_excess))}."
            )
        else:
            paragraphs.append(
                f"The portfolio's weighted return of {fmt_pct(pw_ret)} matched "
                f"the {results['benchmark_ticker']} benchmark."
            )

    # Top drivers
    if ranked:
        top = ranked[:3]
        top_names = ", ".join(h["ticker"] for h in top)
        paragraphs.append(f"Top contributors to outperformance: **{top_names}**.")
        bottom = ranked[-3:]
        bottom_names = ", ".join(h["ticker"] for h in bottom)
        paragraphs.append(f"Largest laggards vs benchmark: **{bottom_names}**.")

    # Concentration
    if valid:
        top_weight = valid[0]["weight"] if valid else 0
        top_ticker = valid[0]["ticker"] if valid else ""
        if top_weight > 30:
            paragraphs.append(
                f"**Concentration risk**: {top_ticker} represents "
                f"{fmt_pct(top_weight)} of the portfolio."
            )
        top3_weight = sum(h["weight"] for h in valid[:3])
        if top3_weight > 60:
            top3_names = ", ".join(h["ticker"] for h in valid[:3])
            paragraphs.append(
                f"The top 3 positions ({top3_names}) account for "
                f"{fmt_pct(top3_weight)} of total value."
            )

    # Data quality
    n_issues = len(results["data_issues"])
    if n_issues:
        paragraphs.append(
            f"**Data caveat**: {n_issues} holding(s) had incomplete or "
            f"missing data — see the Data Issues section for details."
        )

    return paragraphs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Compare stock/portfolio returns against benchmarks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Ticker list mode\n"
            "  python compare_returns.py AAPL MSFT --start 2023-01-01 --end 2024-01-01\n\n"
            "  # Portfolio spreadsheet mode\n"
            "  python compare_returns.py --input portfolio.csv --output report.md\n"
            "  python compare_returns.py --input portfolio.xlsx --benchmark VOO --period 6m\n"
        ),
    )

    # Ticker list mode
    parser.add_argument(
        "tickers",
        nargs="*",
        default=[],
        help="Stock tickers to compare (ticker-list mode)",
    )

    # Portfolio mode
    parser.add_argument(
        "--input",
        "-i",
        dest="input_file",
        help="Path to CSV or Excel file with holdings",
    )

    # Common options
    parser.add_argument(
        "--benchmark",
        default=DEFAULT_BENCHMARK,
        help=f"Benchmark ticker (default: {DEFAULT_BENCHMARK})",
    )
    parser.add_argument(
        "--benchmarks", nargs="+", help="Multiple benchmark tickers (ticker-list mode)"
    )
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--period",
        default=DEFAULT_PERIOD,
        help=f"Lookback period (default: {DEFAULT_PERIOD})",
    )
    parser.add_argument("--output", "-o", help="Output path (.md or .json)")
    parser.add_argument(
        "--top-n",
        type=int,
        default=TOP_N,
        help=f"Number of top/bottom holdings to show (default: {TOP_N})",
    )

    args = parser.parse_args()

    start_date, end_date = resolve_dates(args.start, args.end, args.period)

    # ---- Portfolio spreadsheet mode ----
    if args.input_file:
        logger.info(f"Loading holdings from {args.input_file}")
        holdings = load_holdings(args.input_file)
        logger.info(f"Loaded {len(holdings)} holdings")

        results = analyze_portfolio(holdings, args.benchmark, start_date, end_date)
        report_md = generate_markdown_report(results, args.input_file, top_n=args.top_n)

        output_path = args.output or "output/report.md"
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(report_md)
        logger.info(f"Markdown report written to {output_path}")

        # Also print a brief summary to stdout
        print(f"\n{'='*60}")
        print(f"  Portfolio: {os.path.basename(args.input_file)}")
        print(f"  Period:    {start_date} to {end_date}")
        print(
            f"  Benchmark: {args.benchmark} ({fmt_pct(results['benchmark_stats']['total_return_pct'])})"
        )
        print(
            f"  Portfolio weighted return: {fmt_pct(results['portfolio_weighted_return_pct'])}"
        )
        print(
            f"  Excess vs benchmark:      {fmt_pct(results['portfolio_weighted_excess_pct'])}"
        )
        print(f"  Report: {output_path}")
        print(f"{'='*60}\n")

        return

    # ---- Ticker list mode ----
    if not args.tickers:
        parser.error("Provide either --input FILE or a list of tickers.")

    benchmarks = args.benchmarks or [args.benchmark]
    results = compare_tickers(
        tickers=[t.upper() for t in args.tickers],
        benchmarks=[b.upper() for b in benchmarks],
        start_date=start_date,
        end_date=end_date,
    )

    print_comparison(results)

    if args.output:
        save_results_to_json(results, args.output)
        logger.info(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
