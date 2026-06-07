# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repo has two largely independent halves:

1. **`webapp/` + Docker** — a Flask demo that trades through Interactive Brokers' Client Portal Web API (live/paper brokerage).
2. **`core/`** — a standalone Python backtesting and portfolio-analysis framework using Yahoo Finance historical data. It does **not** depend on the webapp or IBKR; it runs locally with its own venv.

The two share a design idea: `PortfolioManagerBase` (`core/portfolio_manager_base.py`) is an abstract interface meant to let strategies run against either a simulated portfolio or a live IBKR one, but only the simulated `PortfolioManager` exists today.

---

## Part 1 — IBKR Web App (`webapp/`, Docker)

The app never talks to IBKR directly. It talks to the **IBKR Client Portal Gateway** (a Java process) on `localhost:5055`, which proxies authenticated requests to `https://api.ibkr.com`. Everything runs in one Docker container.

### Running
```bash
docker-compose up                  # build + start gateway and Flask app
docker exec -it ibkr bash          # shell into the container (also: ./docker_ssh.sh)
```
`start.sh` (the container CMD) launches both processes:
1. Gateway from `/app/gateway/bin/run.sh` using `root/conf.yaml` (port **5055**, HTTPS).
2. Flask via `flask --app app run --debug -p 5056 -h 0.0.0.0` in a venv (port **5056**, user-facing).

### Authentication (manual, interactive)
There is no programmatic login. The user browses to `https://localhost:5055` and logs in through IBKR's web UI; the gateway holds the session. The Flask app then issues unauthenticated-looking REST calls to `localhost:5055` which the gateway signs. The dashboard route returns a "log in first" message if no session exists.

### Key files & conventions
- **`webapp/app.py`** — the entire Flask app; each route maps a page to gateway REST calls and renders a Jinja template. Edit this for almost all webapp feature work.
- **`webapp/templates/`** — Jinja2 + Bootstrap 5 (CDN); `layout.html` is the base with the nav bar.
- All REST calls go to `BASE_API_URL = "https://localhost:5055/v1/api"` with `verify=False` (self-signed cert; SSL verification disabled app-wide). The commented `keytool`/`openssl` block in the `Dockerfile` is the path to a real cert.
- `ACCOUNT_ID` comes from the `IBKR_ACCOUNT_ID` env var, set in `docker-compose.yml`; it must match a real IBKR account for order/portfolio routes.
- `webapp/` is bind-mounted, so `app.py`/template edits hot-reload. Changes to `conf.yaml`, `Dockerfile`, or `scripts/` require a rebuild.
- **`scripts/rest_api_examples.py`** — standalone scratchpad (mostly commented snippets) for exploring the API; run inside the container.
- `webapp/requirements.txt` lists `flask`/`requests`, but `start.sh` pip-installs those two inline rather than from the file — so adding a webapp dependency means editing `start.sh` (and rebuilding), not just the requirements file.

---

## Part 2 — Backtesting Framework (`core/`)

A pip-installable-style package (imported as `core`) for event-driven backtesting and portfolio return analysis. Pure Python, runs locally — independent of Docker and the webapp.

### Setup & running
```bash
cd core
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt    # pandas, numpy, yfinance, openpyxl, flask, requests

python3 backtests/test_basic.py        # smoke test (also runnable from repo root as core/backtests/test_basic.py)
python3 backtests/example_backtest.py  # full worked examples
```
There is no pytest/unittest harness. `backtests/test_basic.py` is a hand-rolled sequential smoke test that exits non-zero on the first failure — run it as a whole; there is no "single test" selector. Both scripts insert the repo root onto `sys.path`, so they work from either `core/` or the repo root. Note `test_basic.py` and `example_backtest.py` hit the live Yahoo Finance API (unless cache hits cover the requested ranges).

### Architecture
`BacktestEngine` (`core/backtest_engine.py`) is the orchestrator. Its `run()` is the core loop:
1. Merge all symbols' timestamps into one sorted timeline.
2. For each timestamp: update portfolio prices → execute pending orders → fill into portfolio → call `strategy.on_data(timestamp, data)` with history-up-to-now → turn returned signals into orders (market orders execute immediately) → record equity.
3. At the end, `PerformanceAnalytics` computes metrics and `_generate_results()` returns one results dict (summary, metrics, equity curve, transactions, positions, orders).

Components (re-exported from `core/__init__.py`: `DataProvider`, `PortfolioManager`, `PortfolioManagerBase`, `PositionBase`, `OrderManager`, `Order`, `OrderType`, `OrderSide`, `OrderStatus`, `BacktestEngine`, `StrategyBase`, `PerformanceAnalytics`. Concrete strategies and `core.utils` are **not** re-exported here — import them from `core.strategies` / `core.utils`):
- **`DataProvider`** (`data_provider.py`) — fetches OHLCV from Yahoo Finance (`yfinance`) and **caches every fetch as CSV** keyed by `{symbol}_{start}_{end}_{interval}.csv`. The cache dir default is the **CWD-relative** `simulation/data/cache`, so the committed caches under `core/simulation/data/cache/` only resolve when scripts run from `core/`. Delete them or call `clear_cache()` to force refetch.
- **`OrderManager`** (`order_manager.py`) — `Order` dataclass + execution logic for MARKET/LIMIT/STOP/STOP_LIMIT, applying configurable commission and slippage. Order validation happens in `Order.__post_init__`.
- **`PortfolioManager`** (`portfolio_manager.py`) — concrete impl of `PortfolioManagerBase`; tracks cash, positions, transactions, realized/unrealized P&L, and equity history.
- **`StrategyBase`** (`core/strategies/strategy_base.py`) — abstract base. **Subclass and implement `on_data()`** to return a list of signal dicts (`{symbol, side, quantity, order_type, limit_price?, stop_price?}`); helpers like `create_market_order`/`create_limit_order`, `has_position`, `get_historical_data`, `get_current_price`, `get_position_quantity` (current share count) and `get_position_size` (risk-based share sizer) are provided. Optional `on_start()`/`on_end()` hooks. Concrete strategies: `BuyAndHoldStrategy`, `MovingAverageCrossoverStrategy` (registered in `core/strategies/__init__.py`).
- **`PerformanceAnalytics`** (`analytics.py`) — Sharpe, max drawdown, total return, etc., from the equity curve.
- **`core/utils/`** (package, not a module) — `helpers.py` provides `save_results_to_json`/`load_results_from_json`, `format_currency`/`format_percent`, `calculate_date_range`, `validate_date_format`, `print_results_summary`. Used by `example_backtest.py` and `compare_returns.py`. Example output is committed at `core/simulation/data/{buy_and_hold,moving_average}_results.json`.

**Adding a strategy:** create a `StrategyBase` subclass in `core/strategies/`, implement `on_data()`, and add it to `core/strategies/__init__.py`.

### Portfolio comparison tool (`core/backtests/compare_returns.py`)
A separate CLI (not part of the backtest engine) that compares holdings against a benchmark. Two modes:
```bash
# Ticker-list mode — quick terminal comparison vs SPY
python core/backtests/compare_returns.py AAPL MSFT GOOGL --period 1y

# Portfolio mode — reads a CSV/Excel of holdings, writes a markdown report
python core/backtests/compare_returns.py --input core/backtests/input/sample_portfolio.csv
```
Input needs at least `Ticker` and `MarketValue` columns (flexible aliases accepted). Returns are decomposed into price vs dividend return. Full docs: `core/backtests/COMPARE_RETURNS.md`. Ticker normalization for Yahoo Finance handles cases like `BRK.B` → `BRK-B`.
