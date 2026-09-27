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

Without `--output`, files go to a new `outputs/cnbc/YYYYMMDD-YYYYMMDD/` directory, for example `outputs/cnbc/20260907-20260926/`. Repeated runs use `_2`, `_3`, etc. An explicit `--output` is used exactly as supplied. The end date is inclusive. Successfully processed messages are marked read. Future Codex sessions should verify that the cookie file exists, test whether the Keychain item is accessible without exposing it, and ask only for missing run dates or ambiguous overrides; the Drive destination below is already authorized. CNBC cookies can expire and may need to be exported again.

### Google Drive delivery (Codex runs)

The standing destination is [CNBC Jim Cramer Emails](https://drive.google.com/drive/folders/14upHfHyOBPOxarmprZYO1eKMiFQGL4Zd), folder ID `14upHfHyOBPOxarmprZYO1eKMiFQGL4Zd`.

1. Use the connected Google Drive plugin to verify the parent folder before extraction. If unavailable, report the delivery blocker rather than claiming Drive delivery. No Drive credentials belong in this repository.
2. Run the launcher with the confirmed inclusive dates. Keep the printed absolute output directory as the staging directory for this run. Do not upload files from previous runs or any cookies, credentials, logs, or debug HTML.
3. Create a dedicated child folder named from the effective dates as `YYYYMMDD-YYYYMMDD`. Check existing children first; for a separate run with the same dates, use the next available `_2`, `_3`, etc. suffix. On an upload retry, reuse the original run's folder instead of creating another.
4. Upload each generated `.md` file using `google_drive_upload_file`, preserving its filename and Markdown format (`text/markdown`), with the new folder ID as `parent_folder_id`. Do not convert files to Google Docs.
5. Persist the returned folder ID and each successful file ID in a local delivery receipt under the run's staging directory. On retries, verify these IDs and upload only missing files. Never upload the receipt itself. If a request has an uncertain outcome, list the destination and reconcile filenames and sizes before retrying.
6. Verify the destination listing against the run's Markdown filenames and byte sizes. Report the verified Drive folder link, uploaded count, extraction warnings, and any missing uploads. Keep local files if delivery fails; retry delivery from staging without rerunning Gmail extraction. Emails are already marked read after their local files are written.

The shell launcher performs extraction and local staging only. Drive delivery is a required follow-up performed by Codex through the connected Drive plugin; a standalone Terminal invocation does not upload automatically. An empty extraction produces no Drive folder; report that no files were generated.

## Starting future Codex sessions

Open the cloned repository root in Codex. Root-level `AGENTS.md` supplies the branch, safety, launcher, output, and verification rules automatically.
