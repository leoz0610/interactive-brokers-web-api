# Scripts

Utility scripts for working with Interactive Brokers data and portfolio analysis.

## Setup

Python 3.9+ required. Create a virtual environment and install dependencies:

```bash
cd scripts
python3 -m venv venv
source venv/bin/activate
pip install pandas requests
```

Or if the virtual environment already exists:

```bash
source scripts/venv/bin/activate
```

---

## 1. Portfolio Snapshot (`portfolio_snapshot.py`)

Ingests multiple CSV files from different portfolio/account sources and outputs standardized CSV snapshots across six categories plus a summary.

### Quick Start

```bash
# Basic usage with sample data
python scripts/portfolio_snapshot.py \
  --input-dir scripts/sample_input \
  --output-dir scripts/sample_output

# With debug logging
python scripts/portfolio_snapshot.py \
  --input-dir scripts/sample_input \
  --output-dir scripts/sample_output \
  --debug

# Create empty output files for categories with no data
python scripts/portfolio_snapshot.py \
  --input-dir scripts/sample_input \
  --output-dir scripts/sample_output \
  --create-empty

# Include money market funds (SPAXX, VMFXX) in security portfolios
python scripts/portfolio_snapshot.py \
  --input-dir scripts/sample_input \
  --output-dir scripts/sample_output \
  --include-money-market-in-securities
```

### CLI Reference

```
usage: portfolio_snapshot.py [-h] --input-dir INPUT_DIR --output-dir OUTPUT_DIR
                             [--create-empty]
                             [--include-money-market-in-securities]
                             [--debug]
```

| Flag | Description |
|------|-------------|
| `--input-dir` | **(required)** Directory containing input CSV files |
| `--output-dir` | **(required)** Directory for output snapshot CSVs |
| `--create-empty` | Create output files even when no data is found for a category |
| `--include-money-market-in-securities` | Include money market funds in security portfolios instead of cash |
| `--debug` | Enable debug logging |

### Input Format

Place CSV files in the input directory. The script infers each file's type from its filename:

| Filename Pattern | Category |
|-----------------|----------|
| `*stock*`, `*growth*` | Growth portfolio |
| `*etf*`, `*defensive*`, `*fixed_income*` | Defensive portfolio |
| `*household*`, `*家家账本*` | Overall (also extracts cash + retirement rows) |
| `*cash*` | Cash accounts |
| `*retirement*`, `*401k*`, `*ira*` | Retirement accounts |
| `*mortgage*`, `*property*`, `*real_estate*` | Mortgage / real estate |

Column names are normalized automatically. For example, all of these map to the same field:

- `Current Value`, `Market Value`, `MV`, `Value`, `Balance` -> value
- `Ticker`, `Symbol` -> ticker
- `Shares`, `Quantity`, `Qty` -> shares

### Sample Input Files

The `sample_input/` directory contains example CSVs:

**`stock_portfolio.csv`** — Growth stocks (same schema as `compare_returns.py` input):
```csv
Ticker,MarketValue,Shares,CostBasis,Return,Percent
NVDA,"124,033.00",500,"14,568.41",751.38%,20.87%
AAPL,"89,200.00",400,"32,000.00",178.75%,15.01%
```

**`etf_defensive.csv`** — Defensive ETFs with yield:
```csv
Ticker,MarketValue,Shares,CostBasis,Return,Percent,Rate
SCHD,"42,500.00",300,"35,000.00",21.43%,14.28%,3.52%
JEPI,"31,000.00",500,"28,000.00",10.71%,10.41%,7.12%
```

**`household.csv`** — Overall household accounts:
```csv
Account Type,Balance,Percent,Rate
Chase Checking,"40,734.30",3.80%,
Ally Savings,"50,000.00",4.67%,4.25%
Sili 401k,"125,000.00",11.67%,
```

**`retirement.csv`** — Retirement accounts:
```csv
Account Type,Balance,Percent
Sili 401k,"125,000.00",67.13%
Sili Roth IRA,"7,681.96",4.13%
```

**`mortgage.csv`** — Mortgage and property data:
```csv
Account Type,Principal Paid,Remaining Principal,Original Principal,Interest Paid,Interest Paid Beginning of Year,Redfin Estimates
Redmond Home,"137,416.59","1,374,879.41","1,512,296.00","285,000.00","12,500.00","1,877,384.00"
```

### Output Files

| File | Schema |
|------|--------|
| `growth_portfolio_snapshot.csv` | Ticker, MarketValue, Shares, CostBasis, ReturnPercent, AllocationPercent, Rate, SourceFile |
| `defensive_portfolio_snapshot.csv` | Ticker, MarketValue, Shares, CostBasis, ReturnPercent, AllocationPercent, Rate, SourceFile |
| `cash_accounts_snapshot.csv` | AccountName, AccountCategory, Balance, Rate, AllocationPercent, SourceFile |
| `retirement_accounts_snapshot.csv` | AccountName, AccountCategory, Balance, AllocationPercent, SourceFile |
| `mortgage_snapshot.csv` | PropertyName, PrincipalPaid, RemainingPrincipal, OriginalPrincipal, InterestPaid, InterestPaidBeginningOfYear, InterestPaidYTD, EstimatedValue, SourceFile |
| `overall_snapshot.csv` | AccountName, AccountCategory, Balance, Rate, AllocationPercent, SourceFile |
| `summary_totals.csv` | Metric, Value |

### Example Output

Running against sample data:

```bash
python scripts/portfolio_snapshot.py \
  --input-dir scripts/sample_input \
  --output-dir scripts/sample_output \
  --debug
```

Produces `summary_totals.csv`:
```csv
Metric,Value
TotalGrowthPortfolioValue,415733.0
TotalDefensivePortfolioValue,159312.0
TotalCashValue,160734.3
TotalRetirementValue,186181.96
TotalRemainingMortgagePrincipal,1729879.41
TotalEstimatedPropertyValue,2502384.0
EstimatedNetWorth,1694465.85
```

### Parsing Rules

- `$`, `,`, `%` are stripped from numeric values
- Parenthetical negatives: `(123)` becomes `-123`
- Invalid values (`#DIV/0!`, `--`) become null
- Percentages stay as-is: `8.10%` becomes `8.10`, NOT `0.081`
- Rows containing "Total", "Net Worth", "Deposit", "Withdraw", "S&P500", or "Changes" are filtered out
- Options (Call/Put) and negative-share positions are excluded
- Duplicate accounts across files are deduplicated (later source file wins)
- UTF-8 encoding preferred; GBK fallback for Chinese filenames

---

## 2. REST API Examples (`rest_api_examples.py`)

Demonstrates basic usage of the Interactive Brokers Client Portal Web API.

### Prerequisites

The IB Gateway or Client Portal must be running (default: `https://localhost:5055`).

### Usage

```bash
# Start the IB Gateway first (via Docker)
docker-compose up -d

# Run the examples
python scripts/rest_api_examples.py
```

This script shows how to:
- Authenticate and get account info
- Query contract details
- Fetch market data history
- Place limit orders

Most examples are commented out by default. Uncomment the sections you want to run.

---

## Directory Structure

```
scripts/
├── README.md                  # This file
├── portfolio_snapshot.py      # Portfolio snapshot extraction tool
├── rest_api_examples.py       # IB Web API usage examples
└── sample_input/              # Sample CSV data for portfolio_snapshot.py
    ├── stock_portfolio.csv
    ├── etf_defensive.csv
    ├── household.csv
    ├── retirement.csv
    └── mortgage.csv
```
