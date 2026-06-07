# CNBC Investment Club Email Extractor

A standalone Python CLI that reads emails under a Gmail label, extracts CNBC
Investment Club article links, fetches each article with an authenticated CNBC
session, and writes one markdown file per email. Successfully processed emails
are marked as read.

This tool is **independent** of the rest of the repo (webapp and `core/`).

## Setup

```bash
cd cnbc_extractor
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Requires Python 3.10+.

## Gmail prerequisites

- IMAP must be enabled in Gmail settings.
- Use a **Google App Password** (not your normal password and not OAuth). Create
  one at <https://myaccount.google.com/apppasswords>.

## Usage

```bash
python main.py --label "CNBC/InvestmentClub" \
    --start 2026-01-01 --end 2026-06-01 --output ./cnbc_articles
```

`--label`, `--start`, `--end`, and `--output` are CLI arguments. `--label`
defaults to `CNBC/InvestmentClub` and `--output` to `./output`; if you omit
`--start` or `--end` you're prompted for them. The email/username and the two
passwords are resolved **once per run**:

```
Gmail email: user@gmail.com
Gmail app password: ****          # masked (getpass)
CNBC username: user@example.com
CNBC password: ****               # masked (getpass)
```

Dates use `YYYY-MM-DD`. The end date is inclusive.

### Skipping the password prompts

To avoid typing the passwords each run, export them as environment variables;
the script reads them when set and only prompts for any that are missing:

```bash
export GMAIL_APP_PASSWORD="abcdefghijklmnop"   # the 16-char Gmail app password
export CNBC_PASSWORD="your-cnbc-password"
python main.py --start 2026-01-01 --end 2026-06-01
```

Keep these out of version control. Prefer setting them in your shell session or
a password manager rather than a committed file; if you use a `.env`, add it to
`.gitignore` first.

## Output

One markdown file per email, named `{YYYY-MM-DD}_{sanitized-subject}.md`
(collisions get `_2`, `_3`, …). Each file lists the email metadata followed by
each extracted article (title, source URL, plain-text content). Emails with no
CNBC links still produce a file noting that. Articles that fail to fetch/extract
get a placeholder block instead of aborting the run.

## Adjusting the CNBC login flow

CNBC's sign-in flow changes over time and may use CSRF tokens or a different
endpoint. `cnbc_client.py` defines `LOGIN_PAGE_URL` and `LOGIN_POST_URL` plus a
heuristic auth check (`_looks_authenticated`). If login fails:

1. Open the CNBC Investment Club login page in a browser with dev-tools open.
2. Inspect the login form's `action` URL and field names, and any hidden/CSRF
   tokens or redirect parameters.
3. Update `LOGIN_PAGE_URL` / `LOGIN_POST_URL` and the payload field names
   (`email`, `password`, `csrf`) in `cnbc_client.py` to match.

## Files

| File | Responsibility |
|---|---|
| `main.py` | CLI parsing, credential prompts, orchestration, summary |
| `gmail_client.py` | IMAP connect, fetch by label+date, mark as read |
| `cnbc_client.py` | `requests.Session` login + authenticated article fetch |
| `extractor.py` | Email link discovery + readability article extraction |
| `writer.py` | Markdown formatting and file writing |
