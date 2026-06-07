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

## CNBC authentication (cookie-based — required)

CNBC is protected by **Akamai Bot Manager**, which blocks programmatic
username/password login from `requests` (you'll get HTTP 403/503 no matter how
correct the credentials are). There is therefore **no CNBC password option** —
authentication is done by reusing your browser's logged-in session via exported
cookies, passed with the required `--cookies` argument.

The tool verifies the cookies grant authenticated access before processing any
emails. Cookies expire, so re-export them when you start seeing the sign-in wall
again. Both **Netscape `cookies.txt`** and **JSON** cookie exports are accepted.

### Exporting CNBC cookies from Chrome

Use a cookie-export extension (Chrome doesn't export cookies to a file on its
own):

1. In Chrome, log in to the CNBC Investing Club at
   <https://www.cnbc.com/investingclub/> and confirm you can read a members
   article.
2. Install a cookie-export extension from the Chrome Web Store — either:
   - **"Get cookies.txt LOCALLY"** → exports the Netscape `cookies.txt` format, or
   - **"Cookie-Editor"** → use its *Export* button for JSON.
3. With a `cnbc.com` tab focused, click the extension's icon and **Export**.
   - *Get cookies.txt LOCALLY*: choose "Export" → saves `cookies.txt`. Make sure
     it captures the current site (cnbc.com); "Export As → Current Site" is fine.
   - *Cookie-Editor*: click **Export** (clipboard/JSON), then paste into a file,
     e.g. `cnbc_cookies.json`.
4. Save the file somewhere outside the repo (it contains your live session — see
   the security note below) and pass its path to `--cookies`:

   ```bash
   python main.py --cookies ~/cnbc_cookies.txt \
       --start 2026-01-01 --end 2026-06-01
   ```

> **Security:** an exported cookie file is as sensitive as your password — anyone
> with it can use your CNBC session. Keep it out of version control and delete it
> when you're done (or store it in a protected location).

## Usage

```bash
python main.py --cookies ~/cnbc_cookies.txt \
    --start 2026-01-01 --end 2026-06-01 --output ./cnbc_articles
```

CLI arguments:

- `--cookies` (**required**) — path to your exported CNBC cookies file; see the
  CNBC authentication section above.
- `--label` defaults to `CNBC/InvestmentClub`.
- `--output` defaults to `./output`.
- `--gmail-email` defaults to `chensili.uestc@gmail.com`.
- If you omit `--start` or `--end` you're prompted for them.

The only secret resolved at runtime is the Gmail app password — masked via
`getpass` (CNBC uses the cookie file, not a password):

```
Gmail app password: ****          # masked (getpass)
```

Override the Gmail account when needed:

```bash
python main.py --cookies ~/cnbc_cookies.txt --gmail-email me@gmail.com \
    --start 2026-01-01 --end 2026-06-01
```

Dates use `YYYY-MM-DD`. The end date is inclusive.

### Skipping the Gmail password prompt

To avoid typing the Gmail app password each run, export it as an environment
variable; the script reads it when set and prompts only if it's missing:

```bash
export GMAIL_APP_PASSWORD="abcdefghijklmnop"   # the 16-char Gmail app password
python main.py --cookies ~/cnbc_cookies.txt --start 2026-01-01 --end 2026-06-01
```

Keep this out of version control. Prefer setting it in your shell session or a
password manager rather than a committed file; if you use a `.env`, add it to
`.gitignore` first.

## Output

One markdown file per email, named `{YYYY-MM-DD}_{sanitized-subject}.md`
(collisions get `_2`, `_3`, …). Each file lists the email metadata followed by
each extracted article (title, source URL, plain-text content). Emails with no
CNBC links still produce a file noting that. Articles that fail to fetch/extract
get a placeholder block instead of aborting the run.

## Troubleshooting CNBC access

- **"sign-in wall" error on startup** — your cookies are stale or didn't capture
  the logged-in session. Re-log in via Chrome and re-export (see above).
- **`Article ... returned HTTP 403`** during a run — Akamai challenged that
  page. Re-export fresh cookies; if it persists, the article may need a real
  browser. The cookie file's `VERIFY_URL` check passing but articles 403-ing
  means the session aged out mid-run.

`cnbc_client.py` exposes `VERIFY_URL` (the members page used to confirm auth) if
you need to point the check at a different URL.

## Files

| File | Responsibility |
|---|---|
| `main.py` | CLI parsing, Gmail password prompt, orchestration, summary |
| `gmail_client.py` | IMAP connect, fetch by label+date, mark as read |
| `cnbc_client.py` | Cookie-based auth + authenticated article fetch |
| `extractor.py` | Email link discovery + readability article extraction |
| `writer.py` | Markdown formatting and file writing |
