"""CNBC Investment Club client (cookie-based auth).

CNBC sits behind Akamai Bot Manager, which blocks programmatic username/password
logins from `requests` (you get HTTP 403/503 regardless of correct credentials).
So authentication here is **cookie-based**: log in once in a normal browser,
export the cnbc.com cookies, and load them into the session. The same cookies
also carry the Akamai clearance needed to fetch article pages.

See README.md for how to export cookies from Chrome.
"""

import json
from http.cookiejar import LoadError, MozillaCookieJar

import requests

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Members-only page used to verify that loaded cookies are actually authenticated.
VERIFY_URL = "https://www.cnbc.com/investingclub/"

REQUEST_TIMEOUT = 30


class CnbcLoginError(RuntimeError):
    """Raised when authentication to CNBC fails."""


class CnbcClient:
    def __init__(self, cookies_file: str):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        self._load_cookies(cookies_file)
        self._verify_cookie_auth()

    # ------------------------------------------------------------------ #
    # Cookie loading
    # ------------------------------------------------------------------ #
    def _load_cookies(self, path: str) -> None:
        """Load cookies from any of three formats, auto-detected:

        1. JSON cookie export (browser extensions),
        2. Netscape cookies.txt,
        3. a raw `Cookie:` request-header string copied from DevTools, e.g.
           `name1=value1; name2=value2` (the no-extension method — see README).
        """
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = fh.read()
        except (OSError, UnicodeDecodeError) as exc:
            raise CnbcLoginError(f"Could not read cookies file '{path}': {exc}")

        stripped = raw.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            loaded = self._load_cookies_json(raw)
        elif "# Netscape" in raw or "# HTTP Cookie File" in raw or "\t" in raw:
            loaded = self._load_cookies_netscape(path)
        else:
            loaded = self._load_cookies_header(raw)

        if not loaded:
            raise CnbcLoginError(
                f"No cookies could be loaded from '{path}'. Expected a JSON "
                "export, a Netscape cookies.txt, or a raw 'Cookie:' header line."
            )

        domains = {c.domain for c in self.session.cookies}
        print(
            f"Loaded {loaded} cookie(s) from {path} "
            f"across domains: {', '.join(sorted(domains))}"
        )

    def _load_cookies_json(self, raw: str) -> int | None:
        """Load a JSON cookie export (e.g. 'Cookie-Editor' / 'EditThisCookie').

        Returns the count loaded, or None if the text isn't usable JSON.
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None

        # Accept either a bare list or {"cookies": [...]}.
        if isinstance(data, dict) and "cookies" in data:
            data = data["cookies"]
        if not isinstance(data, list):
            return None

        count = 0
        for c in data:
            if not isinstance(c, dict) or "name" not in c or "value" not in c:
                continue
            self.session.cookies.set(
                c["name"],
                c["value"],
                domain=c.get("domain", ".cnbc.com"),
                path=c.get("path", "/"),
            )
            count += 1
        return count

    def _load_cookies_header(self, raw: str) -> int:
        """Parse a raw `Cookie:` request-header string into the session.

        Accepts the value with or without a leading 'Cookie:' label, e.g.
        `Cookie: a=1; b=2` or `a=1; b=2`. All cookies are scoped to .cnbc.com.
        """
        text = raw.strip()
        # Tolerate a pasted "Cookie:" / "cookie:" prefix.
        if text.lower().startswith("cookie:"):
            text = text.split(":", 1)[1].strip()

        count = 0
        for pair in text.split(";"):
            pair = pair.strip()
            if not pair or "=" not in pair:
                continue
            name, value = pair.split("=", 1)
            name, value = name.strip(), value.strip()
            if not name:
                continue
            self.session.cookies.set(
                name, value, domain=".cnbc.com", path="/"
            )
            count += 1
        return count

    def _load_cookies_netscape(self, path: str) -> int:
        """Load a Netscape-format cookies.txt via http.cookiejar."""
        jar = MozillaCookieJar()
        try:
            jar.load(path, ignore_discard=True, ignore_expires=True)
        except (LoadError, OSError) as exc:
            raise CnbcLoginError(
                f"Could not parse cookies file '{path}' as Netscape format: {exc}"
            )
        self.session.cookies.update(jar)
        return len(jar)

    # ------------------------------------------------------------------ #
    # Verification
    # ------------------------------------------------------------------ #
    def _verify_cookie_auth(self) -> None:
        """Confirm the loaded cookies grant authenticated access."""
        try:
            resp = self.session.get(VERIFY_URL, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            raise CnbcLoginError(
                f"Could not reach CNBC to verify cookies: {exc}"
            ) from exc

        if resp.status_code >= 400:
            raise CnbcLoginError(
                f"Cookie verification request failed (HTTP {resp.status_code}).\n"
                + self._describe_response(resp)
            )

        if self._looks_like_signin_wall(resp.text):
            raise CnbcLoginError(
                "Loaded cookies do not appear to be authenticated — CNBC still "
                "shows a sign-in wall. Re-export fresh cookies after logging in "
                "to the Investing Club in your browser (see README)."
            )
        print("CNBC cookie authentication verified.")

    @staticmethod
    def _looks_like_signin_wall(html: str) -> bool:
        """Heuristic: does the page push sign-in/subscribe rather than content?"""
        lowered = (html or "").lower()
        markers = (
            "sign in to continue",
            "subscribe to cnbc investing club",
            "start your subscription",
            "create your free account",
        )
        return any(m in lowered for m in markers)

    @staticmethod
    def _describe_response(resp: requests.Response) -> str:
        """Human-readable dump of a failed response: telltale headers + a body
        snippet. Helps distinguish bot-blocking (Akamai) from a real auth error.
        """
        interesting = ("server", "content-type", "x-akamai-", "akamai",
                       "set-cookie", "retry-after", "x-reference-error")
        header_lines = []
        for key, value in resp.headers.items():
            if any(key.lower().startswith(p) or p in key.lower()
                   for p in interesting):
                header_lines.append(f"    {key}: {value}")

        body = (resp.text or "").strip().replace("\n", " ")
        snippet = body[:400] + ("…" if len(body) > 400 else "")

        akamai_hint = ""
        blob = (body + " ".join(header_lines)).lower()
        if "akamai" in blob or "reference #" in blob or "access denied" in blob:
            akamai_hint = (
                "\n  >> This looks like Akamai bot protection blocking the "
                "request. Re-export fresh cookies from a browser where you're "
                "logged in (see README).")

        return (
            "  --- response headers ---\n"
            + ("\n".join(header_lines) or "    (none of interest)")
            + "\n  --- body snippet ---\n    "
            + (snippet or "(empty)")
            + akamai_hint
        )

    # ------------------------------------------------------------------ #
    # Fetching
    # ------------------------------------------------------------------ #
    def fetch_article(self, url: str) -> str | None:
        """GET an article URL with the authenticated session; return HTML or None."""
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            print(f"  [warn] Failed to fetch article {url}: {exc}")
            return None

        if resp.status_code >= 400:
            print(f"  [warn] Article {url} returned HTTP {resp.status_code}")
            return None
        return resp.text

    def close(self) -> None:
        self.session.close()
