"""Diagnostic for the CNBC extractor: see exactly why a given email yields the
articles (or empty output) that it does.

Two layers, matching the two places extraction can go wrong:

  1. Link discovery (Gmail only) — dumps every <a href> in the email, its link
     text, and the filter verdict (kept, or which rule dropped it). Use this when
     the markdown says "No CNBC article links found" to see whether the article
     link survived discovery.
  2. Full pipeline (needs --cookies) — for each kept link, reproduces main.py:
     fetch → stub-detect/follow → extract → meaningfulness, printing each
     verdict and a content snippet. Use this when links ARE found but no content
     ends up in the markdown (the usual cause: extraction returns empty/junk).
     Add --dump-dir to save each fetched page so you can inspect the raw HTML
     structure (e.g. where the article body actually lives).

Examples:
    # link discovery only (no CNBC cookies needed)
    python debug_links.py --match "Cardinal Health" --start 2026-05-01 --end 2026-05-01

    # full fetch+extract pipeline, saving fetched HTML for inspection
    python debug_links.py --match "Cardinal Health" --start 2026-05-01 --end 2026-05-01 \
        --cookies ~/cnbc_cookies.txt --dump-dir /tmp/cnbc_dump

The Gmail app password is read from $GMAIL_APP_PASSWORD or prompted for.
"""

import argparse
import getpass
import os
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

import extractor as ex
from gmail_client import GmailClient


def explain(url: str) -> str:
    """Return a one-line verdict for a raw href: kept, or which filter dropped it."""
    raw = ex._strip_trailing_punctuation(url.strip())
    if not raw:
        return "DROP: empty"
    if not ex._is_cnbc_url(raw):
        return f"DROP: not a cnbc.com url (host={urlsplit(raw).netloc})"
    dest = ex._resolve_destination(raw)
    if not ex._is_cnbc_url(dest):
        return f"DROP: resolved dest not cnbc.com (dest={dest})"
    path = urlsplit(dest).path.rstrip("/").lower()
    if path in ex._LANDING_PATHS:
        return f"DROP: landing path ({path!r})  dest={dest}"
    hit = next((f for f in ex._NON_ARTICLE_PATH_FRAGMENTS if f in path + "/"), None)
    if hit:
        return f"DROP: non-article fragment {hit!r} in path  dest={dest}"
    return f"KEEP  dest={dest}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="CNBC investing")
    ap.add_argument("--match", required=True, help="substring of the email subject")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--gmail-email", default="chensili.uestc@gmail.com")
    ap.add_argument("--cookies", help="optional: also run the full fetch+extract "
                    "pipeline per kept link, like main.py does")
    ap.add_argument("--dump-dir", help="optional: save fetched HTML for inspection")
    args = ap.parse_args()

    pw = os.environ.get("GMAIL_APP_PASSWORD") or getpass.getpass("Gmail app password: ")
    gmail = GmailClient(args.gmail_email, pw)
    try:
        emails = gmail.fetch_emails(args.label, args.start, args.end)
    finally:
        gmail.close()

    matches = [e for e in emails if args.match.lower() in (e.get("subject") or "").lower()]
    if not matches:
        print(f"No email matched {args.match!r} in {args.start}..{args.end}.")
        return 1

    for em in matches:
        print("=" * 78)
        print("SUBJECT:", em.get("subject"))
        html = em.get("body_html")
        text = em.get("body_text")
        print(f"has html body: {bool(html)}  has text body: {bool(text)}")

        anchors = []
        if html:
            soup = BeautifulSoup(html, "lxml")
            anchors = [a["href"] for a in soup.find_all("a", href=True)]
        print(f"\n--- {len(anchors)} raw anchor href(s) ---")
        for href in anchors:
            label = " ".join(BeautifulSoup(
                str(BeautifulSoup(html, "lxml").find("a", href=href)), "lxml"
            ).get_text(" ", strip=True).split())[:60] if html else ""
            print(f"\n  href: {href}")
            print(f"  text: {label!r}")
            print(f"  -> {explain(href)}")

        kept = ex.extract_links_from_email(html, text)
        print(f"\n--- extractor kept {len(kept)} link(s) ---")
        for u in kept:
            print("  ", u)

        if args.cookies:
            _run_pipeline(kept, args.cookies, args.dump_dir)
    return 0


def _run_pipeline(links: list[str], cookies_file: str, dump_dir: str | None) -> None:
    """Reproduce main.py's per-link fetch+extract, printing each verdict."""
    import os as _os
    from cnbc_client import CnbcClient, CnbcLoginError

    if dump_dir:
        _os.makedirs(dump_dir, exist_ok=True)

    print("\n" + "#" * 78)
    print("# FULL PIPELINE (fetch + extract), mirroring main.py")
    print("#" * 78)
    try:
        cnbc = CnbcClient(cookies_file=cookies_file)
    except CnbcLoginError as exc:
        print(f"CNBC auth failed: {exc}")
        return
    try:
        for url in links:
            print(f"\n>>> {url}")
            html = cnbc.fetch_article(url)
            if html is None:
                print("    fetch -> None (would be a FAILED block)")
                continue
            print(f"    fetched {len(html)} bytes; "
                  f"signin_wall={CnbcClient._looks_like_signin_wall(html)}; "
                  f"stub={ex.is_stub_page(html)}")
            if ex.is_stub_page(html):
                real = ex.find_article_link(html, base_url=url)
                print(f"    stub -> follow: {real}")
                if real:
                    real_html = cnbc.fetch_article(real)
                    if real_html is not None:
                        html = real_html
                        print(f"    followed, fetched {len(html)} bytes; "
                              f"signin_wall={CnbcClient._looks_like_signin_wall(html)}")
            if dump_dir:
                fname = _os.path.join(
                    dump_dir,
                    urlsplit(url).path.strip("/").replace("/", "_")[-80:] or "index"
                ) + ".html"
                with open(fname, "w", encoding="utf-8") as fh:
                    fh.write(html)
                print(f"    dumped -> {fname}")
            extracted = ex.extract_article_content(html)
            content = extracted["content"]
            meaningful = ex.is_meaningful_content(content)
            print(f"    title: {extracted['title']!r}")
            print(f"    content: {len(content)} chars; meaningful={meaningful}")
            snippet = " ".join(content.split())[:300]
            print(f"    snippet: {snippet!r}")
            if not meaningful:
                print("    => WOULD BE SKIPPED (this is why articles ends up empty)")
            else:
                print("    => would be KEPT")
    finally:
        cnbc.close()


if __name__ == "__main__":
    raise SystemExit(main())
