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
again. Three input formats are accepted and auto-detected:

- a **raw `Cookie:` header** string (the no-extension method below),
- a **Netscape `cookies.txt`** file, or
- a **JSON** cookie export.

### Exporting CNBC cookies from Chrome DevTools (no extension needed)

If you can't install browser extensions, copy the cookies straight out of
DevTools. You must use the **Network tab's request header** — *not* the console's
`document.cookie`, because CNBC's login cookies are `HttpOnly` and invisible to
JavaScript.

1. In Chrome, log in to the CNBC Investing Club at
   <https://www.cnbc.com/investingclub/> and confirm you can read a members
   article.
2. Open DevTools: **View → Developer → Developer Tools**, or press
   **⌘+⌥+I** (Mac) / **F12** (Windows).
3. Click the **Network** tab. Tick **Preserve log** (optional but helpful).
4. **Reload the page** (⌘+R / F5) so requests appear.
5. In the request list, click the top **document** request — usually named
   `investingclub/` or `www.cnbc.com` (filter by **Doc** if needed).
6. In the **Headers** panel, scroll to **Request Headers** and find the line
   starting with **`Cookie:`**. (If you only see "Provisional headers", reload
   again with the Network tab already open.)
7. Right-click that `Cookie:` line → **Copy value** (or select the whole value
   after `Cookie:` and copy it).
8. Paste it into a plain text file, e.g. `~/cnbc_cookies.txt`. The leading
   `Cookie:` label is fine to include or omit — both are accepted. The content
   looks like:

   ```
   region=US; _abck=...; bm_sz=...; userid=...; session_token=...; ...
   ```

9. Run the tool pointing at that file:

   ```bash
   python main.py --cookies ~/cnbc_cookies.txt \
       --start 2026-01-01 --end 2026-06-01
   ```

> **Security:** this file contains your live CNBC session — it's as sensitive as
> your password. Save it outside the repo, keep it out of version control, and
> delete it when you're done.

(If you *can* install an extension, "Get cookies.txt LOCALLY" → Netscape
`cookies.txt`, or "Cookie-Editor" → JSON export, both work as `--cookies` inputs
too.)

## Usage

```bash
python main.py --cookies ~/cnbc_cookies.txt \
    --start 2026-01-01 --end 2026-06-01 --output ./cnbc_articles
```

CLI arguments:

- `--cookies` (**required**) — path to your exported CNBC cookies file; see the
  CNBC authentication section above.
- `--label` defaults to `CNBC investing`.
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

### Noise filtering

Newsletter emails are full of non-analysis chrome, which is filtered out so the
markdown only contains Jim's actual commentary:

- **Link level** — CNBC tracking redirects are decoded to their real
  destination, and links to stock-quote pages (`/quotes/...`), the Investing
  Club homepage, and disclaimer/terms/privacy/unsubscribe pages are dropped. The
  same article linked multiple times is fetched once.
- **Content level** — boilerplate paragraphs (newsletter sign-up, the
  "Charitable Trust" list, the trade-alert policy, the "SUBJECT TO OUR TERMS …
  DISCLAIMER" notice) are stripped, and any link whose page is pure boilerplate
  (a disclaimer-only page, a quote data dump, the nav strip) is skipped entirely.

Some newsletter links point to a "view in browser" (`/public/...`) **stub** page
that only contains the headline and a *READ MORE* link, not the article. The tool
detects these stubs and follows the READ MORE link to the real cnbc.com article
before extracting. (For pages that do carry the body but in table-based HTML,
which readability mis-parses, it also falls back to a table-aware sweep.)

The run summary reports how many links were skipped as non-analysis. To tune the
filters, edit the marker lists at the top of `extractor.py`
(`_NON_ARTICLE_PATH_FRAGMENTS`, `_BOILERPLATE_MARKERS`, `_JUNK_MARKERS`,
`_LEGAL_MARKERS`).

## Debugging extraction (`debug_links.py`)

When an email produces empty or wrong output, use `debug_links.py` to see exactly
where the pipeline breaks, without re-running the whole tool. It targets a single
email by subject substring and works in two layers:

1. **Link discovery** (Gmail only — no CNBC cookies needed). Dumps every `<a
   href>` in the email, its link text, and the filter verdict (kept, or which
   rule dropped it). Use this when the markdown says *"No CNBC article links
   found"* to confirm whether the article link even survived discovery.

   ```bash
   python debug_links.py --match "Cardinal Health" --start 2026-05-01 --end 2026-05-01
   ```

2. **Full fetch + extract pipeline** (add `--cookies`). For each kept link it
   reproduces `main.py`: fetch → stub-detect/follow → extract → meaningfulness,
   printing each verdict and a content snippet. Use this when links *are* found
   but no content lands in the markdown — it shows whether the page is a sign-in
   wall, a stub that wasn't followed, or (the common case) an article whose body
   extracts to empty. Add `--dump-dir` to save each fetched page so you can
   inspect the raw HTML structure (e.g. where the article body actually lives).

   ```bash
   python debug_links.py --match "Cardinal Health" --start 2026-05-01 --end 2026-05-01 \
       --cookies ~/cnbc_cookies.txt --dump-dir /tmp/cnbc_dump
   ```

The Gmail app password is read from `$GMAIL_APP_PASSWORD` or prompted for, same as
`main.py`. This script is a developer aid only; it isn't part of the normal run.

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
| `debug_links.py` | Developer diagnostic: dump an email's links + filter verdicts, and optionally run the full fetch/extract pipeline (see "Debugging extraction") |
