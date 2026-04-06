# Portfolio Return Comparison Tool

A command-line tool that compares stock returns against a benchmark index. Supports two modes: quick ticker comparisons and full portfolio analysis from a spreadsheet.

## Setup

Install dependencies (from the project root):

```bash
pip install pandas numpy yfinance openpyxl
```

Or using the existing virtual environment:

```bash
source core/venv/bin/activate
```

## Quick Start

```bash
# Compare a few tickers against SPY over the last year
python core/backtests/compare_returns.py AAPL MSFT GOOGL --period 1y

# Analyze a portfolio spreadsheet and generate a markdown report
python core/backtests/compare_returns.py --input core/backtests/input/sample_portfolio.csv
```

## Modes of Operation

### 1. Ticker List Mode

Pass tickers as positional arguments for a quick terminal comparison.

```bash
# Basic: compare AAPL and NVDA against SPY (default benchmark), trailing 1 year
python core/backtests/compare_returns.py AAPL NVDA

# Specify explicit date range
python core/backtests/compare_returns.py AAPL MSFT GOOGL --start 2023-01-01 --end 2024-01-01

# Use multiple benchmarks
python core/backtests/compare_returns.py AAPL TSLA --benchmarks SPY QQQ

# 6-month lookback
python core/backtests/compare_returns.py AMZN META --period 6m

# Save results to JSON
python core/backtests/compare_returns.py AAPL MSFT --start 2024-01-01 --end 2025-01-01 --output results.json
```

Example output:

```
Period: 2024-01-01 to 2025-01-01

Symbol     Type              Start        End     Return     Annual        Vol     Max DD
-----------------------------------------------------------------------------------------
SPY        Benchmark       $472.65    $592.44    +25.35%    +25.35%    +12.80%     -8.45%
-----------------------------------------------------------------------------------------
AAPL       Ticker          $185.33    $243.85    +31.57%    +31.57%    +22.10%    -16.23%
MSFT       Ticker          $374.72    $421.40    +12.46%    +12.46%    +24.55%    -14.08%
```

### 2. Portfolio Spreadsheet Mode

Pass a CSV or Excel file with `--input` to get a full markdown report.

```bash
# Default: 1-year lookback, SPY benchmark, output to output/report.md
python core/backtests/compare_returns.py --input portfolio.csv

# Custom benchmark and period
python core/backtests/compare_returns.py --input portfolio.xlsx --benchmark VOO --period 6m

# Specify output path
python core/backtests/compare_returns.py \
  --input core/backtests/input/sample_portfolio.csv \
  --output core/backtests/output/my_report.md

# Explicit date range with a different benchmark
python core/backtests/compare_returns.py \
  --input portfolio.csv \
  --start 2023-06-01 --end 2024-06-01 \
  --benchmark IVV \
  --output analysis.md
```

## Input File Format

The spreadsheet (CSV or Excel) needs at minimum a **Ticker** and **MarketValue** column.

### Required Columns

| Column | Description |
|---|---|
| Ticker | Stock ticker symbol (e.g. AAPL, MSFT) |
| MarketValue | Current market value of the position |

### Optional Columns

| Column | Description |
|---|---|
| Shares | Number of shares held |
| CostBasis | Total cost basis of the position |
| Portfolio | Portfolio or account label |

### Example CSV

```csv
Ticker,MarketValue,Shares,CostBasis,Portfolio
AAPL,45000,200,38000,Growth
MSFT,38000,120,32000,Growth
GOOGL,32000,180,28000,Growth
NVDA,25000,50,15000,Growth
TSLA,15000,45,18000,Speculative
JPM,12000,55,10000,Value
```

A sample file is included at `core/backtests/input/sample_portfolio.csv`.

### Column Name Flexibility

The tool recognizes common variations automatically:

| Canonical | Also Accepts |
|---|---|
| Ticker | Symbol, Stock, Stock_Ticker |
| MarketValue | Market Value, Market_Value, Current Value, Value |
| Shares | Quantity, Qty |
| CostBasis | Cost Basis, Cost_Basis, Cost, Avg_Cost |

Matching is case-insensitive and ignores leading/trailing whitespace.

## CLI Reference

```
python core/backtests/compare_returns.py [tickers ...] [options]

Positional arguments:
  tickers                   Stock tickers for ticker-list mode

Options:
  --input, -i FILE          CSV or Excel file with holdings (portfolio mode)
  --output, -o PATH         Output path (.md for report, .json for data)
  --benchmark TICKER        Benchmark ticker (default: SPY)
  --benchmarks T1 T2 ...    Multiple benchmarks (ticker-list mode only)
  --start YYYY-MM-DD        Start date
  --end YYYY-MM-DD          End date
  --period PERIOD            Lookback period (default: 1y)
  -h, --help                Show help
```

### Period Format

| Value | Meaning |
|---|---|
| `1y` | 1 year (default) |
| `6m` | 6 months |
| `3m` | 3 months |
| `90d` | 90 days |
| `2y` | 2 years |
| `1w` | 1 week |

If both `--start` and `--period` are omitted, defaults to trailing 1 year from today.

## Benchmark Options

Any valid Yahoo Finance ticker works. Common choices:

| Ticker | Index |
|---|---|
| SPY | S&P 500 ETF (default) |
| VOO | Vanguard S&P 500 ETF |
| IVV | iShares S&P 500 ETF |
| QQQ | Nasdaq 100 ETF |
| DIA | Dow Jones ETF |
| ^GSPC | S&P 500 Index (not an ETF) |

## Report Structure

The generated markdown report includes:

1. **Overview** -- analysis metadata, total market value, portfolio weighted return, benchmark return, excess return
2. **Holdings Summary** -- table with each holding's return, weight, and excess vs benchmark
3. **Top Outperformers** -- top 5 holdings by excess return
4. **Top Underperformers** -- bottom 5 holdings by excess return
5. **Portfolio Insights** -- narrative summary of drivers, laggards, and concentration risk
6. **Data Issues** -- any tickers with missing or incomplete data

## Edge Case Handling

The tool handles these gracefully without crashing:

- Invalid or delisted tickers (marked as ERROR in the report)
- Recently listed stocks with less than a full year of history (marked as PARTIAL)
- Duplicate tickers (market values are summed)
- Blank rows (skipped)
- Missing or non-numeric market values (treated as 0)
- Missing MarketValue column (all weights default to 0)
