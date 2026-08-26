# Family portfolio snapshot report contract

Use this contract for every new or refreshed family-portfolio snapshot report. It applies to Google Sheets and standalone spreadsheet exports.

## Reference layout

The canonical reference is the Google Sheet **Family Portfolio Snapshot — DRAFT — 2026-08-24**:

https://docs.google.com/spreadsheets/d/1EJqnk0S1kyU0xxV2ni4t-bbT0wlnyPHNfMafJhXEdaY/edit

Preserve its tab structure and visual conventions when they remain applicable: `Summary`, `Accounts`, `Positions`, `Real Estate & Debt`, and `Sources & Checks`. The requirements below override an older reference snapshot if it lacks the new weight column or dedicated ownership category.

## Account classification

Each account must contribute to exactly one reporting category.

1. Normalize `Owner` for comparison by trimming whitespace and comparing case-insensitively.
2. If `Owner` is `Leyi`, set the reporting category to `Leyi owned assets`.
3. Otherwise, use the account's source `Category` as its reporting category.
4. Preserve the original `Owner` and `Category` fields in the account registry. If a helper field is used, label it `Reporting category` and calculate it from those source fields.

The ownership override applies to all Leyi-owned accounts, including cash, brokerage, retirement, or future account types. Do not identify Leyi assets from account names or account IDs when an `Owner` field is available.

## Summary asset-category table

The Summary tab must contain these columns:

| Asset category | Balance | Weight |
|---|---:|---:|
| Cash | formula | formula |
| Growth | formula | formula |
| Defensive | formula | formula |
| RSU | formula | formula |
| Retirement | formula | formula |
| Leyi owned assets | formula | formula |
| Total financial assets | formula | formula |

Include other non-Leyi categories when present in the account registry; do not silently drop them. Category ordering should follow the report's existing convention, with `Leyi owned assets` immediately before the total row.

### Balance rules

- Calculate each category balance from the Accounts registry using the effective reporting category.
- Calculate `Total financial assets` directly from all included account balances.
- Leyi-owned balances must be included in total financial assets exactly once.
- Do not include primary-home value, mortgage balance, home equity, or other real-estate/debt values in this table or its weight denominator.

### Weight rules

- For every category row, calculate `Weight = category balance / Total financial assets`.
- The total row must display 100% when total financial assets are nonzero.
- Guard against a zero denominator so a blank portfolio does not produce a formula error.
- Store weights as numeric formulas and format them as percentages, normally to one decimal place. Do not store formatted percentage text.
- Reconcile the category balance sum to total financial assets and the category weight sum to 100%, allowing only display-rounding differences.

## Formula pattern

Use auditable spreadsheet formulas tied to the actual generated ranges or tables. A helper `Reporting category` column is preferred because it keeps Summary formulas simple.

Conceptually:

```text
Reporting category = IF(LOWER(TRIM(Owner))="leyi", "Leyi owned assets", Category)
Category balance   = SUMIF(Reporting category range, category label, Balance range)
Category weight    = IF(Total financial assets=0, 0, Category balance/Total financial assets)
```

Use the destination spreadsheet's exact row bounds or structured table references. Do not copy fixed row limits from the reference snapshot when the generated account count differs.

## Validation before delivery

- Confirm every populated account maps to one reporting category.
- Confirm all Leyi-owned accounts map to `Leyi owned assets` and nowhere else.
- Confirm the category balances sum to total financial assets.
- Confirm category weights sum to 100% before display rounding.
- Scan for formula errors and visually verify that the new Weight column and all category labels are legible.
- Report any account with missing or ambiguous ownership instead of guessing an ownership override.
