"""CNBC Investment Club Email Extractor — CLI entry point.

Fetches Gmail messages under a label/date range, extracts CNBC article links,
fetches each article via an authenticated CNBC session, and writes one markdown
file per email. Successfully processed emails are marked as read.

Usage:
    python main.py --label "CNBC/InvestmentClub" \
        --start 2026-01-01 --end 2026-06-01 --output ./cnbc_articles
"""

import argparse
import getpass
import os
import sys
from datetime import datetime

# Environment variables that, when set, supply the passwords so you don't have
# to type them every run. If unset, the script falls back to an interactive
# getpass prompt.
GMAIL_PASSWORD_ENV = "GMAIL_APP_PASSWORD"
CNBC_PASSWORD_ENV = "CNBC_PASSWORD"

from cnbc_client import CnbcClient, CnbcLoginError
from extractor import extract_article_content, extract_links_from_email
from gmail_client import GmailClient
from writer import write_email_markdown


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract CNBC Investment Club articles linked in Gmail emails."
    )
    parser.add_argument(
        "--label",
        default="CNBC/InvestmentClub",
        help="Gmail label (default: CNBC/InvestmentClub)",
    )
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--output",
        default="./output",
        help="Output directory (default: ./output)",
    )
    return parser.parse_args()


def _prompt_if_missing(value: str | None, prompt: str) -> str:
    while not value:
        value = input(prompt).strip()
    return value


def _password_from_env_or_prompt(env_var: str, prompt: str) -> str:
    """Return the password from `env_var` if set, else prompt with getpass."""
    value = os.environ.get(env_var)
    if value:
        print(f"Using password from ${env_var}.")
        return value
    return getpass.getpass(prompt)


def _validate_date(date_str: str, field: str) -> str:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        sys.exit(f"Invalid {field} '{date_str}' — expected YYYY-MM-DD.")
    return date_str


def main() -> int:
    args = parse_args()

    label = _prompt_if_missing(args.label, "Gmail label: ")
    start_date = _validate_date(
        _prompt_if_missing(args.start, "Start date (YYYY-MM-DD): "), "start date"
    )
    end_date = _validate_date(
        _prompt_if_missing(args.end, "End date (YYYY-MM-DD): "), "end date"
    )
    output_dir = args.output

    # Credentials — resolved once per run. Passwords come from environment
    # variables when set (see GMAIL_PASSWORD_ENV / CNBC_PASSWORD_ENV), otherwise
    # the user is prompted interactively.
    gmail_email = input("Gmail email: ").strip()
    gmail_password = _password_from_env_or_prompt(
        GMAIL_PASSWORD_ENV, "Gmail app password: "
    )
    cnbc_username = input("CNBC username: ").strip()
    cnbc_password = _password_from_env_or_prompt(
        CNBC_PASSWORD_ENV, "CNBC password: "
    )

    # Connect to Gmail (fatal on failure).
    try:
        gmail = GmailClient(gmail_email, gmail_password)
    except RuntimeError as exc:
        sys.exit(f"ERROR: {exc}")

    # Login to CNBC (fatal on failure).
    try:
        cnbc = CnbcClient(cnbc_username, cnbc_password)
    except CnbcLoginError as exc:
        gmail.close()
        sys.exit(f"ERROR: {exc}")

    total_emails = 0
    processed = 0
    total_articles = 0
    failures = 0

    try:
        emails = gmail.fetch_emails(label, start_date, end_date)
        total_emails = len(emails)
        print(f"Found {total_emails} email(s) in '{label}' "
              f"between {start_date} and {end_date}.")

        for em in emails:
            subject = em.get("subject") or "(no subject)"
            print(f"\nProcessing: {subject}")
            try:
                links = extract_links_from_email(
                    em.get("body_html"), em.get("body_text")
                )
                articles = []
                for url in links:
                    print(f"  Fetching article: {url}")
                    html = cnbc.fetch_article(url)
                    if html is None:
                        articles.append({"url": url, "failed": True})
                        failures += 1
                        continue
                    try:
                        extracted = extract_article_content(html)
                        articles.append(
                            {
                                "url": url,
                                "title": extracted["title"],
                                "content": extracted["content"],
                            }
                        )
                        total_articles += 1
                    except Exception as exc:
                        print(f"  [warn] Extraction failed for {url}: {exc}")
                        articles.append({"url": url, "failed": True})
                        failures += 1

                path = write_email_markdown(
                    output_dir,
                    {
                        "subject": subject,
                        "date": em.get("date"),
                        "from": em.get("from"),
                    },
                    articles,
                    label=label,
                )
                print(f"  Wrote {path}")

                # Only mark read once the file is safely written.
                gmail.mark_as_read(em["uid"])
                processed += 1
            except Exception as exc:
                print(f"  [warn] Failed to process email '{subject}': {exc}")
                failures += 1
                continue
    finally:
        cnbc.close()
        gmail.close()

    print(
        f"\nProcessed {processed}/{total_emails} emails, "
        f"{total_articles} articles extracted, {failures} failures."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
