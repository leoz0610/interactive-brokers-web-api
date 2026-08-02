# Interactive Brokers Web API project instructions

## Purpose

This repository is both the source tree and the persistent Codex workspace for:

1. `core/backtests/compare_returns.py`
2. `cnbc_extractor/main.py`

Keep generated reports and session artifacts in `outputs/`. Do not commit generated reports, virtual environments, credentials, or exported cookies.

## Branch policy

- `customized-changes` is the user's trunk and the default base for work and runs.
- `main` is reserved for syncing from the forked/upstream source.
- At the start of every task, run `git status --short --branch` from the repository root.
- Do not switch to, commit on, merge into, or base work on `main` unless the user explicitly requests upstream synchronization.
- Never discard uncommitted changes. If the tree is dirty, inspect and preserve them.

## Pull request policy

- For work intended for a pull request, create a new feature branch from `customized-changes` and make all iterative changes and commits on that feature branch.
- When the user asks to create a pull request, target `customized-changes` as the pull request's base branch.
- Treat this feature-branch workflow and PR base as the defaults unless the user explicitly requests different behavior.

## Preferred entry points

Use the repository launchers instead of invoking source scripts directly:

- `scripts/run_compare_returns.sh`
- `scripts/run_cnbc_extractor.sh`
- `scripts/setup.sh` for environments and dependencies.

The launchers verify the source branch lineage and keep default output under this repository.

## Compare-returns behavior

- It reads Yahoo Finance and may write JSON or Markdown.
- Confirm tickers, benchmark, period/date range, input file, and output destination when they are not clear.
- Ticker mode does not write unless `--output` is provided.
- Portfolio mode receives a timestamped default report path from the launcher when no output is specified.
- Treat results as analytical estimates, not financial advice. Note missing, partial, or stale market data.

## CNBC extractor behavior and safety

- Requires Python 3.10+, a Gmail App Password, and an exported CNBC cookie file.
- This workstation has Python 3.13 installed at `/usr/local/bin/python3.13`; use `scripts/setup.sh` to create or refresh the repository virtual environments.
- The confirmed Gmail account is `chensili.uestc@gmail.com`, the Gmail label is `CNBC investing`, and the usual cookie file is `/Users/silichen/Documents/cnbc_extract/cookies.txt`. Still confirm the inclusive dates and output location for each run, and verify that the cookie file exists and remains valid.
- The Gmail App Password is stored in macOS Keychain under account `chensili.uestc@gmail.com` and service `cnbc-extractor-gmail`. Retrieve it directly into `GMAIL_APP_PASSWORD` for the extractor process with `security find-generic-password`; never print, log, or write its value. Keychain access may require sandbox escalation or macOS approval.
- A successful normal run writes Markdown and marks processed Gmail messages read.
- Before running, confirm Gmail account, Gmail label, inclusive start/end dates, cookies path, and output location.
- Prefer `cnbc_extractor/debug_links.py` for diagnosis because normal extraction changes Gmail read state.
- Never display, log, commit, or copy secrets into repository files. Cookie files must remain outside this repository.
- Use `GMAIL_APP_PASSWORD` only from the current process environment or a secure credential mechanism; otherwise allow the program's masked prompt.

## Documentation to consult

- Source overview: `CLAUDE.md`
- Returns CLI: `core/backtests/COMPARE_RETURNS.md`
- CNBC first run: `cnbc_extractor/RUNNING.md`
- CNBC reference: `cnbc_extractor/README.md`
- Codex workflow guide: `docs/CODEX_WORKFLOWS.md`

## Verification after runs

- Always report the full, fully expanded command used to produce results. Include the absolute executable and source-script paths, every effective argument, and the explicit output path when applicable; do not report only the launcher command.
- Report effective dates/inputs, output path, and any warnings or failed symbols/articles.
- Check repository status afterward and distinguish generated artifacts from source edits.
- Do not commit or push unless the user explicitly asks.
