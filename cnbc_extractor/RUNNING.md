# Running the CNBC Extractor — First-Run Walkthrough

End-to-end steps for a first run, with both credentials resolved up front so the
run is non-interactive.

> **Note on "passwords":** there are *two* credentials, but only one is a
> password. **Gmail** uses a Google App Password. **CNBC has no password** —
> Akamai Bot Manager blocks programmatic login, so CNBC auth is done with
> **exported browser cookies**, not a password. "Both resolved" therefore means:
> the Gmail App Password + the CNBC cookie file.

## Step 1 — One-time setup (venv + deps)

```bash
cd cnbc_extractor
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Requires Python 3.10+.

## Step 2 — Resolve the Gmail credential (App Password)

1. Enable IMAP in Gmail settings.
2. Create a Google **App Password** (not your normal password, not OAuth) at
   <https://myaccount.google.com/apppasswords> — it's a 16-char string.
3. Export it so you aren't prompted at runtime:

   ```bash
   export GMAIL_APP_PASSWORD="abcdefghijklmnop"   # the 16-char app password
   ```

   If you skip this, the script prompts for it via masked `getpass` at startup
   instead.

## Step 3 — Resolve the CNBC credential (cookie file)

CNBC's login cookies are `HttpOnly`, so you must copy them from the **Network
tab**, not `document.cookie`:

1. In Chrome, log in at <https://www.cnbc.com/investingclub/> and confirm you can
   read a members article.
2. Open DevTools (⌘+⌥+I), go to the **Network** tab.
3. Reload the page (⌘+R) so requests appear.
4. Click the top **document** request (named `investingclub/` or `www.cnbc.com`;
   filter by **Doc** if needed).
5. Under **Request Headers**, find the line starting with `Cookie:`, right-click
   → **Copy value**.
6. Paste it into a plain text file outside the repo, e.g. `~/cnbc_cookies.txt`.
   (The leading `Cookie:` label is optional — both accepted.)

> **Security:** this file is a live session — as sensitive as your password. Keep
> it out of version control and delete it when done.

For the full cookie-export reference (including the Netscape `cookies.txt` and
JSON extension-based alternatives), see the [CNBC authentication
section](README.md#cnbc-authentication-cookie-based--required) of the README.

## Step 4 — Run the extractor

```bash
python main.py --cookies ~/cnbc_cookies.txt \
    --start 2026-01-01 --end 2026-06-01 \
    --output ./cnbc_articles
```

What happens on this first run:

- Reads `$GMAIL_APP_PASSWORD` (set in Step 2) — **no Gmail prompt**.
- Loads `~/cnbc_cookies.txt`, auto-detects its format, and **verifies** it grants
  members access before processing any email (fails fast with a sign-in-wall
  error if the cookies are stale).
- Pulls emails in the `CNBC investing` label (override with `--label`) between
  `--start` and `--end` (`YYYY-MM-DD`, end inclusive), extracts/fetches the linked
  articles, and writes one markdown file per email into `./cnbc_articles`. Each
  email is marked read **only after** its file is written.

Defaults worth knowing: `--label` is `CNBC investing`, `--output` is `./output`,
`--gmail-email` is a hardcoded address (override with `--gmail-email
me@gmail.com`). If you omit `--start`/`--end` you'll be prompted for them.

See the [README](README.md) for output format, noise-filtering internals,
debugging with `debug_links.py`, and CNBC-access troubleshooting.
