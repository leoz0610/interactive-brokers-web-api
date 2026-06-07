"""Link discovery from email bodies and article content extraction from HTML."""

import re

from bs4 import BeautifulSoup
from readability import Document

# Matches bare URLs in plain-text bodies.
_URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)


def _is_cnbc_url(url: str) -> bool:
    return "cnbc.com" in url.lower()


def _strip_trailing_punctuation(url: str) -> str:
    return url.rstrip(".,);]'\"")


def extract_links_from_email(
    html_body: str | None, text_body: str | None
) -> list[str]:
    """Return deduplicated CNBC URLs found in the email body.

    Prefers the HTML body's <a href> links; falls back to regex over the plain
    text body when no HTML is available.
    """
    urls: list[str] = []
    seen: set[str] = set()

    def _add(url: str) -> None:
        url = _strip_trailing_punctuation(url.strip())
        if url and _is_cnbc_url(url) and url not in seen:
            seen.add(url)
            urls.append(url)

    if html_body:
        soup = BeautifulSoup(html_body, "lxml")
        for anchor in soup.find_all("a", href=True):
            _add(anchor["href"])

    # Fall back to (or supplement with) plain-text URLs only if HTML found none.
    if not urls and text_body:
        for match in _URL_RE.findall(text_body):
            _add(match)

    return urls


def extract_article_content(html: str) -> dict:
    """Extract {title, content} from an article's raw HTML.

    Uses readability-lxml to isolate the main article, then BeautifulSoup to
    flatten it to plain text while preserving paragraph breaks.
    """
    doc = Document(html)

    try:
        title = doc.short_title()
    except Exception:
        title = ""

    try:
        summary_html = doc.summary(html_partial=True)
    except Exception:
        summary_html = html

    content = _html_to_text(summary_html)
    return {"title": title or "(untitled)", "content": content}


def _html_to_text(html: str) -> str:
    """Convert HTML to plain text, keeping blank lines between block elements."""
    soup = BeautifulSoup(html, "lxml")

    # Drop non-content elements.
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    blocks = soup.find_all(
        ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote"]
    )
    if blocks:
        paragraphs = []
        for block in blocks:
            text = block.get_text(separator=" ", strip=True)
            if text:
                paragraphs.append(text)
        if paragraphs:
            return "\n\n".join(paragraphs)

    # Fallback: collapse the whole thing, preserving line-based paragraphs.
    text = soup.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n\n".join(lines)
