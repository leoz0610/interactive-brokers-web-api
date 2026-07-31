# Codex investing workflows

This repository contains the persistent Codex instructions, launchers, virtual-environment setup, and output structure needed for repeated portfolio-return comparisons and CNBC Investing Club extraction. Open the repository root as the Codex project folder; no separate `~/Documents/Codex/investing-workflows` folder is required.

## One-time setup

Install Python 3.10 or newer, then run from the repository root:

```bash
./scripts/setup.sh
```

The script creates isolated environments under `.venvs/` and installs each tool's requirements.

## Compare returns

Ticker mode:

```bash
./scripts/run_compare_returns.sh AAPL MSFT GOOGL --period 1y
```

Portfolio mode:

```bash
./scripts/run_compare_returns.sh \
  --input /absolute/path/portfolio.csv \
  --benchmark SPY \
  --period 1y
```

When portfolio mode has no explicit `--output`, the launcher writes a timestamped report under `outputs/returns/`. Pass `--output /path/report.md` to override it.

## CNBC extractor

Keep the CNBC cookies file outside this repository. Export the Gmail App Password for the current shell, or omit it to use the program's masked prompt:

```bash
export GMAIL_APP_PASSWORD="your-app-password"

./scripts/run_cnbc_extractor.sh \
  --cookies /absolute/path/outside/repository/cnbc_cookies.txt \
  --gmail-email you@example.com \
  --label "CNBC investing" \
  --start 2026-01-01 \
  --end 2026-06-01
```

Without `--output`, files go to `outputs/cnbc/`. The end date is inclusive. Successfully processed messages are marked read.

## Starting future Codex sessions

Open the cloned repository root in Codex. Root-level `AGENTS.md` supplies the branch, safety, launcher, output, and verification rules automatically.
