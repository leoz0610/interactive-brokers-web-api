"""Format and write one markdown file per email."""

import os
import re
from datetime import datetime

_MAX_SUBJECT_LEN = 80


def _sanitize_subject(subject: str) -> str:
    """lowercase, spaces→hyphens, strip special chars, truncate to 80."""
    subject = (subject or "").strip().lower()
    subject = re.sub(r"\s+", "-", subject)
    subject = re.sub(r"[^a-z0-9\-]", "", subject)
    subject = re.sub(r"-{2,}", "-", subject).strip("-")
    if not subject:
        subject = "no-subject"
    return subject[:_MAX_SUBJECT_LEN].rstrip("-")


def _format_date(date_value) -> str:
    """Format a datetime as 'YYYY-MM-DD HH:MM'; pass through strings/None."""
    if isinstance(date_value, datetime):
        return date_value.strftime("%Y-%m-%d %H:%M")
    return str(date_value) if date_value else "(unknown)"


def _date_prefix(date_value) -> str:
    if isinstance(date_value, datetime):
        return date_value.strftime("%Y-%m-%d")
    return "0000-00-00"


def _unique_path(output_dir: str, base_name: str) -> str:
    """Return a non-colliding path, appending _2, _3, ... as needed."""
    candidate = os.path.join(output_dir, f"{base_name}.md")
    if not os.path.exists(candidate):
        return candidate
    counter = 2
    while True:
        candidate = os.path.join(output_dir, f"{base_name}_{counter}.md")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def write_email_markdown(
    output_dir: str,
    email_meta: dict,
    articles: list[dict],
    label: str = "",
) -> str:
    """Write a markdown file for one email; return the path written."""
    os.makedirs(output_dir, exist_ok=True)

    subject = email_meta.get("subject") or "(no subject)"
    base_name = f"{_date_prefix(email_meta.get('date'))}_{_sanitize_subject(subject)}"
    path = _unique_path(output_dir, base_name)

    lines: list[str] = []
    lines.append(f"# {subject}")
    lines.append("")
    lines.append(f"- **Date:** {_format_date(email_meta.get('date'))}")
    lines.append(f"- **From:** {email_meta.get('from') or '(unknown)'}")
    lines.append(f"- **Label:** {label}")
    lines.append("")
    lines.append("---")
    lines.append("")

    if not articles:
        lines.append("*No CNBC article links found in this email.*")
        lines.append("")
    else:
        for idx, article in enumerate(articles, start=1):
            url = article.get("url", "")
            if article.get("failed"):
                lines.append(f"## Article {idx}: (failed to extract)")
                lines.append("")
                lines.append(f"**Source:** {url}")
                lines.append("")
                lines.append("> Could not fetch or extract content from this article.")
            else:
                title = article.get("title") or "(untitled)"
                lines.append(f"## Article {idx}: {title}")
                lines.append("")
                lines.append(f"**Source:** {url}")
                lines.append("")
                lines.append(article.get("content") or "")
            lines.append("")
            lines.append("---")
            lines.append("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")

    return path
