"""Link discovery from email bodies and article content extraction from HTML.

Newsletter emails are full of links and boilerplate that aren't Jim's analysis
(stock-quote pages, the Investing Club homepage, disclaimers, terms of service,
newsletter sign-up blurbs, the charitable-trust trade-alert policy, etc.). This
module filters those out at two levels:

  1. Link level — `extract_links_from_email` decodes CNBC's tracking redirects to
     their true destination and drops non-article URLs (quotes, homepage,
     disclaimer/terms/privacy, unsubscribe, app/social links).
  2. Content level — `extract_article_content` strips boilerplate paragraphs, and
     `is_meaningful_content` flags whole "articles" that are just junk so the
     caller can skip them.
"""

import base64
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from readability import Document

# Matches bare URLs in plain-text bodies.
_URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)

# Path fragments whose pages are never Jim's analysis. Checked against the
# *resolved* destination path (after decoding tracking redirects).
_NON_ARTICLE_PATH_FRAGMENTS = (
    "/quotes/",          # stock quote pages
    "/disclaimer",
    "/terms",            # terms of service / terms and conditions
    "/privacy",
    "/unsubscribe",
    "/preferences",
    "/manage-",          # manage subscription / preferences
    "/cookie",
    "/applemusic",
    "/apps",
    "/about-cnbc",
    "/digital-products",
)

# Resolved paths that are landing pages, not articles (matched exactly, ignoring
# a trailing slash). Real articles live deeper, e.g. /investingclub/<slug> or
# /id/<number> or a dated path.
_LANDING_PATHS = {
    "",
    "/",
    "/investingclub",
    "/pro",
}

# Substrings (case-insensitive) marking a boilerplate paragraph to drop.
_BOILERPLATE_MARKERS = (
    "sign up for my",
    "sign up for the",
    "for a full list of the stocks at jim cramer",
    "as a subscriber to the cnbc investing club",
    "you will receive a trade alert",
    "jim waits 45 minutes",
    "the above investing club information is subject to",
    "subject to our terms and conditions",
    "click to read the disclaimer",
    "no fiduciary obligation or duty exists",
    "no specific outcome or profit is guaranteed",
    "(see here for a full list",
    "see jim cramer's top 10",
    "questions, comments, suggestions for the cnbc investing club",
)

# A whole "article" that matches these (and little else) is junk: a quote-page
# data dump or the index/nav strip.
_JUNK_MARKERS = (
    "us eur asia bonds oil gold",   # market nav ticker strip
    "click to read the disclaimer",
)

# Minimum length of meaningful text for an article to be worth keeping.
_MIN_MEANINGFUL_CHARS = 80


def _is_cnbc_url(url: str) -> bool:
    return "cnbc.com" in url.lower()


def _strip_trailing_punctuation(url: str) -> str:
    return url.rstrip(".,);]'\"")


def _resolve_destination(url: str) -> str:
    """Decode CNBC's `link.cnbc.com/click/<id>/<base64>/...` redirects to the
    real destination URL. Returns the input unchanged if it isn't such a link.
    """
    parts = urlsplit(url)
    if "link.cnbc.com" not in parts.netloc or "/click/" not in parts.path:
        return url

    # The destination is the base64 segment after `/click/<id.num>/`.
    segments = [s for s in parts.path.split("/") if s]
    for seg in segments:
        if len(seg) < 16:  # skip the short `click` / id segments
            continue
        decoded = _try_b64(seg)
        if decoded and decoded.lower().startswith("http"):
            return decoded
    return url


def _try_b64(segment: str) -> str | None:
    segment += "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(segment).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def _is_useful_article_url(url: str) -> bool:
    """True if the resolved destination looks like an analysis article (not a
    quote page, landing page, disclaimer, or other newsletter chrome).
    """
    dest = _resolve_destination(url)
    if not _is_cnbc_url(dest):
        return False

    path = urlsplit(dest).path.rstrip("/").lower()
    if path in _LANDING_PATHS:
        return False
    if any(frag in path + "/" for frag in _NON_ARTICLE_PATH_FRAGMENTS):
        return False
    return True


def extract_links_from_email(
    html_body: str | None, text_body: str | None
) -> list[str]:
    """Return deduplicated CNBC *article* URLs found in the email body.

    Tracking redirects are resolved to their true destination for filtering and
    de-duplication, but the original (clickable) URL is returned so the session
    follows the redirect normally. Non-article links (quotes, homepage,
    disclaimer/terms, unsubscribe, etc.) are dropped.
    """
    urls: list[str] = []
    seen_dest: set[str] = set()

    def _add(url: str) -> None:
        url = _strip_trailing_punctuation(url.strip())
        if not url or not _is_cnbc_url(url):
            return
        if not _is_useful_article_url(url):
            return
        # De-duplicate on the resolved destination (ignoring tracking query
        # params) so the same article linked twice isn't fetched twice.
        dest = _resolve_destination(url)
        key = urlsplit(dest)._replace(query="", fragment="").geturl()
        if key in seen_dest:
            return
        seen_dest.add(key)
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
    flatten it to plain text, then strips boilerplate paragraphs (disclaimers,
    terms, newsletter sign-up, trade-alert policy, etc.).
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

    content = _strip_boilerplate(_html_to_text(summary_html))
    return {"title": title or "(untitled)", "content": content}


def is_meaningful_content(content: str) -> bool:
    """False if the (boilerplate-stripped) content is empty or pure junk.

    Lets the caller skip non-analysis "articles" — quote-page data dumps, the
    nav strip, disclaimer-only pages — entirely.
    """
    text = (content or "").strip()
    if len(text) < _MIN_MEANINGFUL_CHARS:
        return False
    lowered = text.lower()
    if any(marker in lowered for marker in _JUNK_MARKERS):
        # Junk marker present and almost nothing else of substance.
        non_junk = lowered
        for marker in _JUNK_MARKERS:
            non_junk = non_junk.replace(marker, "")
        if len(non_junk.strip()) < _MIN_MEANINGFUL_CHARS:
            return False
    return True


def _is_boilerplate_paragraph(paragraph: str) -> bool:
    lowered = paragraph.lower()
    return any(marker in lowered for marker in _BOILERPLATE_MARKERS)


def _strip_boilerplate(text: str) -> str:
    """Drop boilerplate paragraphs (disclaimers, terms, sign-ups) from content."""
    paragraphs = text.split("\n\n")
    kept = [p for p in paragraphs if p.strip() and not _is_boilerplate_paragraph(p)]
    return "\n\n".join(kept).strip()


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
