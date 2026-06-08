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
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from readability import Document

# Matches bare URLs in plain-text bodies.
_URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)

# A real CNBC article path looks like one of these (vs. a /public/ stub, a quote
# page, or a landing page).
_ARTICLE_PATH_RE = re.compile(
    r"(/\d{4}/\d{2}/\d{2}/|/id/\d+|/investingclub/.+|/select/.+|\.html$)",
    re.IGNORECASE,
)

# Markers that identify a "view in browser" stub page rather than the article.
_STUB_MARKERS = (
    "view in browser",
    "latest cramer news",
    "read more",
    "read m ore",
)

# Path fragments whose pages are never Jim's analysis. Checked as substrings of
# the *resolved* destination path (after decoding tracking redirects).
_NON_ARTICLE_PATH_FRAGMENTS = (
    "/quotes/",             # stock quote pages
    "disclaimer",
    "terms-of-service",     # e.g. /nbcuniversal-terms-of-service/
    "terms-of-use",
    "terms-and-conditions",
    "nbcuniversal-terms",
    "/terms",
    "privacy-policy",
    "/privacy",
    "unsubscribe",
    "/preferences",
    "/manage-",             # manage subscription / preferences
    "cookie",
    "/applemusic",
    "/apps",
    "about-cnbc",
    "digital-products",
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
    # Email/page footer chrome.
    "all rights reserved",
    "a versant media company",
    "englewood cliffs",
    "sylvan avenue",
    "data is a real-time snapshot",
    "data is delayed at least",
    "data also provided by",
    "global business and financial news",
    # "View in browser" stub chrome and footer link strip.
    "view in browser",
    "latest cramer news",
    "read more",
    "read m ore",
    "jim cramer twitter",
    "need help with your investing club subscription",
    "manage newsletters",
    "digital products",
    "join the cnbc panel",
    "privacy policy",
    "terms of service",
    "unsubscribe",
    "feedback",
    # Market nav ticker strip.
    "us eur asia bonds oil gold",
)

# The standard Investing Club footer is always appended as a *contiguous tail*
# of Jim's analysis (subscriber blurb → trade-alert policy → "SUBJECT TO OUR
# TERMS … DISCLAIMER" notice). On real cnbc.com article pages the whole body is
# delivered as a single undelimited text block, so per-paragraph stripping would
# discard the entire article. Instead we truncate the text at the earliest of
# these footer-start markers, keeping everything before it. Each marker reliably
# marks the start of that trailing footer, never legitimate mid-article prose.
_FOOTER_MARKERS = (
    "as a subscriber to the cnbc investing club",
    "you will receive a trade alert",
    "jim waits 45 minutes",
    "the above investing club information is subject to",
    "(see here for a full list",
    "see jim cramer's top 10",
    "questions, comments, suggestions for the cnbc investing club",
    "sign up for my",
    "sign up for the",
    "for a full list of the stocks at jim cramer",
)

# A whole "article" that matches these (and little else) is junk: a quote-page
# data dump or the index/nav strip.
_JUNK_MARKERS = (
    "us eur asia bonds oil gold",   # market nav ticker strip
    "click to read the disclaimer",
)

# If content prominently contains these, it's a legal/terms page, not analysis.
_LEGAL_MARKERS = (
    "cnbc+ supplemental terms",
    "cnbc+ services",
    "nbcuniversal terms of service",
    "these terms of service",
    "terms and conditions of use",
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


def canonical_article_key(url: str) -> str:
    """Normalized resolved-destination key for the same article linked via
    different URLs (e.g. a `/public/` "view in browser" stub vs a direct tracking
    redirect). Tracking redirects are decoded and query/fragment dropped, so the
    caller can de-duplicate articles whose duplicate links only become apparent
    after a stub is followed to its real destination.
    """
    dest = _resolve_destination(url)
    return urlsplit(dest)._replace(query="", fragment="").geturl()


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
        key = canonical_article_key(url)
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

    Uses readability-lxml to isolate the main article. When that fails — e.g. the
    table-based HTML of a newsletter "view in browser" (`/public/...`) page,
    where readability often returns only the footer — it falls back to a
    table-aware extraction over the full document. Boilerplate paragraphs
    (disclaimers, terms, newsletter sign-up, footer chrome) are then stripped.
    """
    doc = Document(html)

    try:
        title = doc.short_title()
    except Exception:
        title = ""
    if not title:
        title = _title_from_html(html)

    try:
        summary_html = doc.summary(html_partial=True)
    except Exception:
        summary_html = html

    content = _strip_boilerplate(_html_to_text(summary_html))

    # readability missed the body (common on table-based newsletter pages):
    # fall back to a table-aware sweep of the whole document.
    if not is_meaningful_content(content):
        fallback = _strip_boilerplate(_extract_full_text(html))
        if len(fallback) > len(content):
            content = fallback

    return {"title": title or "(untitled)", "content": content}


def is_stub_page(html: str) -> bool:
    """True if the page is a 'view in browser' stub whose real article is behind
    a READ MORE link (newsletter web versions), not the article itself.
    """
    text = BeautifulSoup(html, "lxml").get_text(separator=" ", strip=True).lower()
    hits = sum(1 for m in _STUB_MARKERS if m in text)
    # A stub has the tell-tale chrome; require "view in browser" plus one more so
    # a real article that merely says "read more" somewhere isn't misclassified.
    return ("view in browser" in text and hits >= 2)


def find_article_link(html: str, base_url: str = "") -> str | None:
    """Return the first real-article link found in a page (e.g. the READ MORE /
    headline link on a stub page). Returns None if none is found.
    """
    soup = BeautifulSoup(html, "lxml")
    for anchor in soup.find_all("a", href=True):
        href = urljoin(base_url, anchor["href"].strip())
        if not _is_cnbc_url(href):
            continue
        dest = _resolve_destination(href)
        path = urlsplit(dest).path
        if "/public/" in path:
            continue
        if not _is_useful_article_url(href):
            continue
        if _ARTICLE_PATH_RE.search(path):
            return href
    return None


def is_meaningful_content(content: str) -> bool:
    """False if the (boilerplate-stripped) content is empty or pure junk.

    Lets the caller skip non-analysis "articles" — quote-page data dumps, the
    nav strip, disclaimer-only pages, and terms/legal pages — entirely.
    """
    text = (content or "").strip()
    if len(text) < _MIN_MEANINGFUL_CHARS:
        return False
    lowered = text.lower()
    if any(marker in lowered for marker in _LEGAL_MARKERS):
        return False
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


def _truncate_at_footer(text: str) -> str:
    """Cut `text` at the earliest Investing Club footer marker.

    Real cnbc.com article bodies arrive as one undelimited block with the
    standard subscriber/disclaimer footer tacked onto the end. Truncating at the
    first footer marker keeps Jim's analysis and drops the footer, even when
    there are no paragraph breaks to strip on.
    """
    lowered = text.lower()
    cut = min(
        (lowered.find(m) for m in _FOOTER_MARKERS if m in lowered),
        default=-1,
    )
    return text[:cut].strip() if cut != -1 else text


def _strip_boilerplate(text: str) -> str:
    """Drop boilerplate from content.

    First truncate the trailing Investing Club footer (handles the single-block
    article bodies CNBC serves), then drop any remaining standalone boilerplate
    paragraphs (disclaimers, terms, sign-ups, nav chrome) from what's left.
    """
    text = _truncate_at_footer(text)
    paragraphs = text.split("\n\n")
    kept = [p for p in paragraphs if p.strip() and not _is_boilerplate_paragraph(p)]
    return "\n\n".join(kept).strip()


def _title_from_html(html: str) -> str:
    """Best-effort title from <title> / og:title / first heading."""
    soup = BeautifulSoup(html, "lxml")
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        return og["content"].strip()
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    for level in ("h1", "h2"):
        h = soup.find(level)
        if h and h.get_text(strip=True):
            return h.get_text(strip=True)
    return ""


def _extract_full_text(html: str) -> str:
    """Table-aware text sweep over the whole document.

    Fallback for pages readability can't parse (e.g. table-based newsletter HTML).
    Removes non-content elements, then collects text from block-level and
    table-cell elements, de-duplicating repeated paragraphs.
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "head", "nav",
                     "header", "footer", "form", "button"]):
        tag.decompose()

    blocks = soup.find_all(
        ["p", "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6",
         "td", "dd", "figcaption"]
    )

    paragraphs: list[str] = []
    seen: set[str] = set()
    for block in blocks:
        # Skip cells that merely wrap other collected blocks (avoid duplication).
        if block.find(["p", "li", "td", "blockquote"]):
            continue
        text = block.get_text(separator=" ", strip=True)
        if len(text) < 2 or text in seen:
            continue
        seen.add(text)
        paragraphs.append(text)

    return "\n\n".join(paragraphs)


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
