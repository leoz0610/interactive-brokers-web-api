# Codex investing workflows

This repository contains the persistent Codex instructions, launchers, virtual-environment setup, and output structure needed for repeated portfolio-return comparisons and CNBC Investing Club extraction. Open the repository root as the Codex project folder; no separate `~/Documents/Codex/investing-workflows` folder is required.

## One-time setup

Install Python 3.10 or newer, then run from the repository root:

```bash
./scripts/setup.sh
```

The script creates isolated environments under `.venvs/` and installs each tool's requirements.

On the current workstation, Python 3.13 is installed at `/usr/local/bin/python3.13`. A virtual environment isolates dependencies but does not replace the underlying Python interpreter, so rerun `./scripts/setup.sh` if `.venvs/` is missing or stale.

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

Keep the CNBC cookies file and Gmail App Password outside this repository. This workstation's reusable configuration is:

- Gmail account: `chensili.uestc@gmail.com`
- Gmail label: `CNBC investing`
- CNBC cookie file: `/Users/silichen/Documents/cnbc_extract/cookies.txt`
- macOS Keychain account: `chensili.uestc@gmail.com`
- macOS Keychain service: `cnbc-extractor-gmail`

The Keychain item can be created or replaced from any Terminal window. The `-w` option prompts securely, so the App Password does not enter shell history:

```bash
security add-generic-password -U \
  -a "chensili.uestc@gmail.com" \
  -s "cnbc-extractor-gmail" \
  -w
```

For a run, retrieve the credential directly into the extractor process. Do not print it or save it in a file:

```bash
GMAIL_APP_PASSWORD="$(security find-generic-password \
  -a 'chensili.uestc@gmail.com' \
  -s 'cnbc-extractor-gmail' \
  -w)" ./scripts/run_cnbc_extractor.sh \
  --cookies /Users/silichen/Documents/cnbc_extract/cookies.txt \
  --gmail-email chensili.uestc@gmail.com \
  --label "CNBC investing" \
  --start 2026-01-01 \
  --end 2026-06-01
```

Without `--output`, files go to `outputs/cnbc/`. The end date is inclusive. Successfully processed messages are marked read. Future Codex sessions should verify that the cookie file exists, test whether the Keychain item is accessible without exposing it, and ask only for the run's date range and any desired output override. CNBC cookies can expire and may need to be exported again.

## Starting future Codex sessions

Open the cloned repository root in Codex. Root-level `AGENTS.md` supplies the branch, safety, launcher, output, and verification rules automatically.
