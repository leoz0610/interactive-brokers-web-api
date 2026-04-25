#!/usr/bin/env python3
"""Portfolio snapshot extraction tool.

Ingests multiple CSV inputs and outputs standardized CSV snapshots
across different portfolio categories.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column name mapping
# ---------------------------------------------------------------------------

COLUMN_ALIASES: dict[str, list[str]] = {
    "ticker": ["ticker", "symbol"],
    "value": ["marketvalue", "current value", "market value", "mv", "value", "balance"],
    "shares": ["shares", "quantity", "qty"],
    "cost_basis": ["costbasis", "cost basis", "total cost basis"],
    "return_pct": ["return", "gain/loss %", "return %"],
    "allocation_pct": ["percent", "allocation", "weight"],
    "rate": ["rate", "yield", "apy"],
    "account_name": ["account type", "account", "name"],
    "principal_paid": ["principal paid"],
    "remaining_principal": ["remaining principal"],
    "original_principal": ["original principal"],
    "interest_paid": ["interest paid"],
    "interest_paid_boy": ["interest paid beginning of year"],
    "interest_paid_ytd": ["interest paid ytd"],
    "property_value": ["redfin estimate", "redfin estimates", "estimated value"],
}

# ---------------------------------------------------------------------------
# Detection keywords
# ---------------------------------------------------------------------------

CASH_KEYWORDS = [
    "cash", "checking", "savings", "bank", "cd", "money market",
    "spaxx", "vmfxx",
]

RETIREMENT_KEYWORDS = ["401k", "ira", "roth", "rollover", "brokeragelink"]

NOISE_KEYWORDS = ["total", "net worth", "deposit", "withdraw", "s&p500", "changes"]

# ---------------------------------------------------------------------------
# Numeric cleaning
# ---------------------------------------------------------------------------


def clean_number(value: object) -> Optional[float]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if s in ("", "--", "#DIV/0!", "N/A", "n/a", "-"):
        return None
    s = s.replace("$", "").replace(",", "").replace("%", "")
    neg = False
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
        neg = True
    try:
        result = float(s)
        return -result if neg else result
    except ValueError:
        return None


def clean_percent(value: object) -> Optional[float]:
    """Return percentage as-is (8.10% -> 8.10), NOT as decimal."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if s in ("", "--", "#DIV/0!", "N/A", "n/a", "-"):
        return None
    s = s.replace("$", "").replace(",", "")
    had_pct = "%" in s
    s = s.replace("%", "")
    neg = False
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
        neg = True
    try:
        result = float(s)
        if neg:
            result = -result
        return result
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Column normalisation
# ---------------------------------------------------------------------------


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    col_map: dict[str, str] = {}
    lower_cols = {c: c.strip().lower() for c in df.columns}
    for canonical, aliases in COLUMN_ALIASES.items():
        for orig_col, low in lower_cols.items():
            if low in aliases and orig_col not in col_map:
                col_map[orig_col] = canonical
    return df.rename(columns=col_map)


# ---------------------------------------------------------------------------
# Row classification helpers
# ---------------------------------------------------------------------------


def _lower(val: object) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip().lower()


def is_total_or_noise_row(row: pd.Series) -> bool:
    text_cols = ["ticker", "account_name"]
    for col in text_cols:
        if col in row.index:
            low = _lower(row[col])
            if any(kw in low for kw in NOISE_KEYWORDS):
                return True
    return False


def is_cash_like(name: str) -> bool:
    low = name.lower()
    return any(kw in low for kw in CASH_KEYWORDS)


def is_retirement_account(name: str) -> bool:
    low = name.lower()
    return any(kw in low for kw in RETIREMENT_KEYWORDS)


def is_option_like(name: str) -> bool:
    low = name.lower()
    return bool(re.search(r"\b(call|put)\b", low))


# ---------------------------------------------------------------------------
# File-type inference
# ---------------------------------------------------------------------------

FILE_TYPE_PATTERNS: dict[str, str] = {
    "growth": "growth",
    "stock": "growth",
    "defensive": "defensive",
    "etf": "defensive",
    "fixed_income": "defensive",
    "household": "overall",
    "家家账本": "overall",
    "cash": "cash",
    "retirement": "retirement",
    "401k": "retirement",
    "ira": "retirement",
    "mortgage": "mortgage",
    "realestate": "mortgage",
    "real_estate": "mortgage",
    "property": "mortgage",
}

MORTGAGE_COLUMNS = {"principal_paid", "remaining_principal", "property_value"}
SECURITY_COLUMNS = {"ticker", "shares", "cost_basis"}


def infer_file_type(path: Path, df: pd.DataFrame) -> str:
    stem = path.stem.lower().replace("-", "_").replace(" ", "_")
    for pattern, ftype in FILE_TYPE_PATTERNS.items():
        if pattern in stem:
            return ftype

    cols = set(df.columns)
    if cols & MORTGAGE_COLUMNS:
        return "mortgage"
    if "ticker" in cols:
        return "growth"
    if "account_name" in cols:
        return "overall"
    return "unknown"


# ---------------------------------------------------------------------------
# Extraction functions
# ---------------------------------------------------------------------------


def _classify_cash_category(name: str) -> str:
    low = name.lower()
    for kw, cat in [
        ("checking", "Checking"),
        ("savings", "Savings"),
        ("cd", "CD"),
        ("money market", "MoneyMarket"),
        ("spaxx", "Cash"),
        ("vmfxx", "Cash"),
        ("cash", "Cash"),
        ("bank", "Bank"),
    ]:
        if kw in low:
            return cat
    return "Other"


def _classify_retirement_category(name: str) -> str:
    low = name.lower()
    if "brokeragelink" in low:
        return "BrokerageLink"
    if "roth" in low:
        return "Roth IRA"
    if "rollover" in low:
        return "Rollover IRA"
    if "401k" in low or "401(k)" in low:
        return "401k"
    if "ira" in low:
        return "IRA"
    return "Retirement Other"


def extract_security_rows(
    df: pd.DataFrame, source_file: str, include_mm_in_securities: bool = False,
) -> list[dict]:
    rows = []
    for _, row in df.iterrows():
        if is_total_or_noise_row(row):
            continue
        ticker = _lower(row.get("ticker"))
        if not ticker:
            continue
        if is_option_like(ticker):
            continue
        if is_cash_like(ticker) and not include_mm_in_securities:
            continue
        shares = clean_number(row.get("shares"))
        if shares is not None and shares < 0:
            continue
        rows.append({
            "Ticker": str(row.get("ticker", "")).strip(),
            "MarketValue": clean_number(row.get("value")),
            "Shares": shares,
            "CostBasis": clean_number(row.get("cost_basis")),
            "ReturnPercent": clean_percent(row.get("return_pct")),
            "AllocationPercent": clean_percent(row.get("allocation_pct")),
            "Rate": clean_percent(row.get("rate")),
            "SourceFile": source_file,
        })
    return rows


def extract_cash_rows(df: pd.DataFrame, source_file: str) -> list[dict]:
    rows = []
    for _, row in df.iterrows():
        if is_total_or_noise_row(row):
            continue
        name = str(row.get("account_name", row.get("ticker", ""))).strip()
        if not name or not is_cash_like(name):
            continue
        rows.append({
            "AccountName": name,
            "AccountCategory": _classify_cash_category(name),
            "Balance": clean_number(row.get("value")),
            "Rate": clean_percent(row.get("rate")),
            "AllocationPercent": clean_percent(row.get("allocation_pct")),
            "SourceFile": source_file,
        })
    return rows


def extract_retirement_rows(df: pd.DataFrame, source_file: str) -> list[dict]:
    rows = []
    for _, row in df.iterrows():
        if is_total_or_noise_row(row):
            continue
        name = str(row.get("account_name", "")).strip()
        if not name or not is_retirement_account(name):
            continue
        rows.append({
            "AccountName": name,
            "AccountCategory": _classify_retirement_category(name),
            "Balance": clean_number(row.get("value")),
            "AllocationPercent": clean_percent(row.get("allocation_pct")),
            "SourceFile": source_file,
        })
    return rows


def extract_mortgage_rows(df: pd.DataFrame, source_file: str) -> list[dict]:
    rows = []
    for _, row in df.iterrows():
        if is_total_or_noise_row(row):
            continue
        name = str(row.get("account_name", "")).strip()
        if not name:
            continue
        rows.append({
            "PropertyName": name,
            "PrincipalPaid": clean_number(row.get("principal_paid")),
            "RemainingPrincipal": clean_number(row.get("remaining_principal")),
            "OriginalPrincipal": clean_number(row.get("original_principal")),
            "InterestPaid": clean_number(row.get("interest_paid")),
            "InterestPaidBeginningOfYear": clean_number(row.get("interest_paid_boy")),
            "InterestPaidYTD": clean_number(row.get("interest_paid_ytd")),
            "EstimatedValue": clean_number(row.get("property_value")),
            "SourceFile": source_file,
        })
    return rows


def extract_overall_rows(df: pd.DataFrame, source_file: str) -> list[dict]:
    rows = []
    for _, row in df.iterrows():
        if is_total_or_noise_row(row):
            continue
        name = str(row.get("account_name", "")).strip()
        if not name:
            continue
        rows.append({
            "AccountName": name,
            "AccountCategory": _classify_account_category(name),
            "Balance": clean_number(row.get("value")),
            "Rate": clean_percent(row.get("rate")),
            "AllocationPercent": clean_percent(row.get("allocation_pct")),
            "SourceFile": source_file,
        })
    return rows


def _classify_account_category(name: str) -> str:
    if is_cash_like(name):
        return _classify_cash_category(name)
    if is_retirement_account(name):
        return _classify_retirement_category(name)
    return "Investment"


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

@dataclass
class SnapshotOutputs:
    growth: list[dict] = field(default_factory=list)
    defensive: list[dict] = field(default_factory=list)
    cash: list[dict] = field(default_factory=list)
    retirement: list[dict] = field(default_factory=list)
    mortgage: list[dict] = field(default_factory=list)
    overall: list[dict] = field(default_factory=list)


def _deduplicate_by_name(rows: list[dict], name_key: str) -> list[dict]:
    """Keep the last occurrence of each account name (later source wins)."""
    seen: dict[str, int] = {}
    for i, row in enumerate(rows):
        key = (row.get(name_key, "") or "").strip().lower()
        if key:
            seen[key] = i
    return [rows[i] for i in sorted(seen.values())]


def _safe_sum(rows: list[dict], key: str) -> float:
    return sum(r.get(key) or 0 for r in rows)


def build_summary(outputs: SnapshotOutputs) -> list[dict]:
    total_growth = _safe_sum(outputs.growth, "MarketValue")
    total_defensive = _safe_sum(outputs.defensive, "MarketValue")
    total_cash = _safe_sum(outputs.cash, "Balance")
    total_retirement = _safe_sum(outputs.retirement, "Balance")
    total_mortgage_remaining = _safe_sum(outputs.mortgage, "RemainingPrincipal")
    total_property_value = _safe_sum(outputs.mortgage, "EstimatedValue")
    net_worth = round(
        total_growth + total_defensive + total_cash + total_retirement
        + total_property_value - total_mortgage_remaining, 2,
    )
    return [
        {"Metric": "TotalGrowthPortfolioValue", "Value": total_growth},
        {"Metric": "TotalDefensivePortfolioValue", "Value": total_defensive},
        {"Metric": "TotalCashValue", "Value": total_cash},
        {"Metric": "TotalRetirementValue", "Value": total_retirement},
        {"Metric": "TotalRemainingMortgagePrincipal", "Value": total_mortgage_remaining},
        {"Metric": "TotalEstimatedPropertyValue", "Value": total_property_value},
        {"Metric": "EstimatedNetWorth", "Value": net_worth},
    ]


# ---------------------------------------------------------------------------
# Output writer
# ---------------------------------------------------------------------------

OUTPUT_SCHEMAS: dict[str, list[str]] = {
    "growth": ["Ticker", "MarketValue", "Shares", "CostBasis", "ReturnPercent",
               "AllocationPercent", "Rate", "SourceFile"],
    "defensive": ["Ticker", "MarketValue", "Shares", "CostBasis", "ReturnPercent",
                  "AllocationPercent", "Rate", "SourceFile"],
    "cash": ["AccountName", "AccountCategory", "Balance", "Rate",
             "AllocationPercent", "SourceFile"],
    "retirement": ["AccountName", "AccountCategory", "Balance",
                   "AllocationPercent", "SourceFile"],
    "mortgage": ["PropertyName", "PrincipalPaid", "RemainingPrincipal",
                 "OriginalPrincipal", "InterestPaid", "InterestPaidBeginningOfYear",
                 "InterestPaidYTD", "EstimatedValue", "SourceFile"],
    "overall": ["AccountName", "AccountCategory", "Balance", "Rate",
                "AllocationPercent", "SourceFile"],
    "summary": ["Metric", "Value"],
}

OUTPUT_FILENAMES: dict[str, str] = {
    "growth": "growth_portfolio_snapshot.csv",
    "defensive": "defensive_portfolio_snapshot.csv",
    "cash": "cash_accounts_snapshot.csv",
    "retirement": "retirement_accounts_snapshot.csv",
    "mortgage": "mortgage_snapshot.csv",
    "overall": "overall_snapshot.csv",
    "summary": "summary_totals.csv",
}


def write_outputs(
    outputs: SnapshotOutputs,
    output_dir: Path,
    create_empty: bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs.cash = _deduplicate_by_name(outputs.cash, "AccountName")
    outputs.retirement = _deduplicate_by_name(outputs.retirement, "AccountName")

    summary_rows = build_summary(outputs)

    datasets: dict[str, list[dict]] = {
        "growth": outputs.growth,
        "defensive": outputs.defensive,
        "cash": outputs.cash,
        "retirement": outputs.retirement,
        "mortgage": outputs.mortgage,
        "overall": outputs.overall,
        "summary": summary_rows,
    }

    for key, rows in datasets.items():
        if not rows and not create_empty:
            logger.info("Skipping %s (no data, --create-empty not set)", key)
            continue
        filename = OUTPUT_FILENAMES[key]
        schema = OUTPUT_SCHEMAS[key]
        df = pd.DataFrame(rows, columns=schema)
        out_path = output_dir / filename
        df.to_csv(out_path, index=False, encoding="utf-8")
        logger.info("Wrote %s (%d rows)", out_path, len(df))


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def process_file(
    path: Path,
    outputs: SnapshotOutputs,
    include_mm_in_securities: bool = False,
) -> None:
    logger.info("Processing %s", path.name)
    try:
        df = pd.read_csv(path, encoding="utf-8")
    except Exception:
        try:
            df = pd.read_csv(path, encoding="gbk")
        except Exception as e:
            logger.warning("Could not read %s: %s", path.name, e)
            return

    df = normalize_columns(df)
    file_type = infer_file_type(path, df)
    source = path.name
    logger.debug("Inferred type=%s for %s", file_type, source)

    if file_type == "growth":
        outputs.growth.extend(
            extract_security_rows(df, source, include_mm_in_securities)
        )
    elif file_type == "defensive":
        outputs.defensive.extend(
            extract_security_rows(df, source, include_mm_in_securities)
        )
    elif file_type == "mortgage":
        outputs.mortgage.extend(extract_mortgage_rows(df, source))
    elif file_type == "retirement":
        outputs.retirement.extend(extract_retirement_rows(df, source))
    elif file_type == "cash":
        outputs.cash.extend(extract_cash_rows(df, source))
    elif file_type == "overall":
        overall = extract_overall_rows(df, source)
        outputs.overall.extend(overall)
        outputs.cash.extend(extract_cash_rows(df, source))
        outputs.retirement.extend(extract_retirement_rows(df, source))
    elif file_type == "unknown":
        logger.warning("Unknown file type for %s — attempting heuristic extraction", source)
        cols = set(df.columns)
        if "ticker" in cols:
            outputs.growth.extend(
                extract_security_rows(df, source, include_mm_in_securities)
            )
        if "account_name" in cols:
            outputs.overall.extend(extract_overall_rows(df, source))
            outputs.cash.extend(extract_cash_rows(df, source))
            outputs.retirement.extend(extract_retirement_rows(df, source))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Extract portfolio snapshots from CSV files.",
    )
    parser.add_argument(
        "--input-dir", type=Path, required=True,
        help="Directory containing input CSV files",
    )
    parser.add_argument(
        "--output-dir", type=Path, required=True,
        help="Directory for output snapshot CSVs",
    )
    parser.add_argument(
        "--create-empty", action="store_true",
        help="Create output files even when no data is found",
    )
    parser.add_argument(
        "--include-money-market-in-securities", action="store_true",
        help="Include money market funds (SPAXX, VMFXX) in security portfolios",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    input_dir: Path = args.input_dir
    if not input_dir.is_dir():
        logger.error("Input directory does not exist: %s", input_dir)
        sys.exit(1)

    csv_files = sorted(input_dir.glob("*.csv"))
    if not csv_files:
        logger.error("No CSV files found in %s", input_dir)
        sys.exit(1)

    logger.info("Found %d CSV file(s) in %s", len(csv_files), input_dir)

    outputs = SnapshotOutputs()
    for path in csv_files:
        process_file(path, outputs, args.include_money_market_in_securities)

    write_outputs(outputs, args.output_dir, args.create_empty)
    logger.info("Done.")


if __name__ == "__main__":
    main()
