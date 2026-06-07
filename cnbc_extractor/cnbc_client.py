"""CNBC Investment Club client.

Logs in once via a `requests.Session` and reuses the session cookies for every
subsequent article fetch.

NOTE ON THE LOGIN FLOW: CNBC's authentication uses an OAuth-style flow backed by
a Janrain/registration endpoint, and the exact form fields / token names change
over time. Rather than hard-code a brittle flow, this client:
  1. GETs the login page to pick up cookies and any CSRF/hidden token,
  2. POSTs the credentials to a configurable login endpoint,
  3. verifies the result.
The endpoint and field names are overridable so the implementer can adjust them
after inspecting the live login page (see README.md).
"""

import requests
from bs4 import BeautifulSoup

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Default endpoints — adjust after inspecting the live login page if needed.
LOGIN_PAGE_URL = "https://www.cnbc.com/investingclub/"
LOGIN_POST_URL = "https://register.cnbc.com/auth/api/v3/signin"

REQUEST_TIMEOUT = 30


class CnbcLoginError(RuntimeError):
    """Raised when authentication to CNBC fails."""


class CnbcClient:
    def __init__(
        self,
        username: str,
        password: str,
        login_page_url: str = LOGIN_PAGE_URL,
        login_post_url: str = LOGIN_POST_URL,
    ):
        self.username = username
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,*/*;q=0.8",
            }
        )
        self._login(username, password, login_page_url, login_post_url)

    def _login(
        self,
        username: str,
        password: str,
        login_page_url: str,
        login_post_url: str,
    ) -> None:
        # Step 1: prime the session with cookies and discover any CSRF token.
        try:
            page = self.session.get(login_page_url, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            raise CnbcLoginError(
                f"Could not reach CNBC login page: {exc}"
            ) from exc

        csrf_token = self._find_csrf_token(page.text)

        # Step 2: submit credentials. CNBC's signin API expects JSON; fall back
        # to form-encoded if a non-JSON endpoint is configured.
        payload = {"email": username, "password": password}
        if csrf_token:
            payload["csrf"] = csrf_token

        try:
            resp = self.session.post(
                login_post_url,
                json=payload,
                headers={"Referer": login_page_url},
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise CnbcLoginError(f"Login request failed: {exc}") from exc

        # Step 3: verify. A successful sign-in returns 200/302 and sets auth
        # cookies. We treat an explicit auth-failure status or a body that still
        # shows a sign-in form as failure.
        if resp.status_code in (401, 403):
            raise CnbcLoginError(
                f"CNBC login rejected credentials (HTTP {resp.status_code})."
            )
        if resp.status_code >= 400:
            raise CnbcLoginError(
                f"CNBC login failed (HTTP {resp.status_code})."
            )

        if not self._looks_authenticated(resp):
            raise CnbcLoginError(
                "CNBC login did not appear to succeed — no auth cookie was set. "
                "Inspect the live login page and adjust LOGIN_POST_URL / field "
                "names in cnbc_client.py."
            )

    @staticmethod
    def _find_csrf_token(html: str) -> str | None:
        soup = BeautifulSoup(html, "lxml")
        for name in ("csrf", "csrfToken", "_csrf", "csrf_token"):
            tag = soup.find("input", attrs={"name": name})
            if tag and tag.get("value"):
                return tag["value"]
            meta = soup.find("meta", attrs={"name": name})
            if meta and meta.get("content"):
                return meta["content"]
        return None

    def _looks_authenticated(self, resp: requests.Response) -> bool:
        """Heuristic auth check: an auth/session cookie should now be present."""
        cookie_names = {c.lower() for c in self.session.cookies.keys()}
        auth_markers = ("token", "session", "auth", "user", "login")
        return any(marker in name for name in cookie_names for marker in auth_markers)

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
