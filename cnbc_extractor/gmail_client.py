"""Gmail IMAP client: connect, fetch emails by label + date range, mark as read.

Uses only stdlib (`imaplib`, `email`). Authentication is via a Gmail App
Password (not the regular account password and not OAuth).
"""

import email
import imaplib
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parsedate_to_datetime

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993


def _imap_date(date_str: str) -> str:
    """Convert 'YYYY-MM-DD' to IMAP's 'DD-Mon-YYYY' (e.g. '02-Jun-2026')."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%d-%b-%Y")


def _imap_date_plus_one(date_str: str) -> str:
    """IMAP BEFORE is exclusive; add a day so the end date is inclusive."""
    dt = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
    return dt.strftime("%d-%b-%Y")


def _decode(value) -> str:
    """Decode a possibly RFC2047-encoded header into a plain string."""
    if value is None:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


class GmailClient:
    def __init__(self, email_address: str, app_password: str):
        self.email_address = email_address
        try:
            self.conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
            self.conn.login(email_address, app_password)
        except (imaplib.IMAP4.error, OSError) as exc:
            raise RuntimeError(f"Gmail connection/login failed: {exc}") from exc

    def _select_label(self, label: str) -> None:
        """Select the mailbox matching a Gmail label.

        Gmail labels map to IMAP folders. Nested labels use '/' (e.g.
        'CNBC/InvestmentClub'). The folder name is quoted to tolerate spaces.
        """
        status, _ = self.conn.select(f'"{label}"', readonly=False)
        if status != "OK":
            # Surface available folders to aid debugging mislabeled mailboxes.
            folders = self._list_folders()
            raise RuntimeError(
                f"Could not select label '{label}'. Available folders:\n  "
                + "\n  ".join(folders)
            )

    def _list_folders(self) -> list[str]:
        status, data = self.conn.list()
        if status != "OK" or not data:
            return []
        names = []
        for raw in data:
            line = raw.decode(errors="replace") if isinstance(raw, bytes) else str(raw)
            # Format: (flags) "delimiter" "folder name"
            if '"' in line:
                names.append(line.rsplit('"', 2)[-2])
            else:
                names.append(line.split()[-1])
        return names

    def fetch_emails(
        self, label: str, start_date: str, end_date: str
    ) -> list[dict]:
        """Return emails in `label` between start_date and end_date (inclusive)."""
        self._select_label(label)

        criteria = (
            f'(SINCE "{_imap_date(start_date)}" '
            f'BEFORE "{_imap_date_plus_one(end_date)}")'
        )
        status, data = self.conn.uid("SEARCH", None, criteria)
        if status != "OK":
            raise RuntimeError(f"IMAP search failed for label '{label}'")

        uids = data[0].split() if data and data[0] else []
        emails: list[dict] = []
        for uid_bytes in uids:
            uid = uid_bytes.decode()
            try:
                emails.append(self._fetch_one(uid))
            except Exception as exc:  # per-email failure shouldn't abort the run
                print(f"  [warn] Failed to fetch email uid={uid}: {exc}")
        return emails

    def _fetch_one(self, uid: str) -> dict:
        status, data = self.conn.uid("FETCH", uid, "(RFC822)")
        if status != "OK" or not data or data[0] is None:
            raise RuntimeError("FETCH returned no data")

        raw = data[0][1]
        msg = email.message_from_bytes(raw)

        subject = _decode(msg.get("Subject"))
        sender = _decode(msg.get("From"))
        date_hdr = msg.get("Date")
        try:
            date_dt = parsedate_to_datetime(date_hdr) if date_hdr else None
        except (TypeError, ValueError):
            date_dt = None

        body_html, body_text = self._extract_bodies(msg)

        return {
            "uid": uid,
            "subject": subject,
            "from": sender,
            "date": date_dt,
            "body_html": body_html,
            "body_text": body_text,
        }

    @staticmethod
    def _extract_bodies(msg: Message) -> tuple[str | None, str | None]:
        """Walk MIME parts; collect first text/html and text/plain bodies."""
        body_html: str | None = None
        body_text: str | None = None

        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disposition = str(part.get("Content-Disposition") or "")
                if "attachment" in disposition.lower():
                    continue
                if ctype == "text/html" and body_html is None:
                    body_html = GmailClient._decode_payload(part)
                elif ctype == "text/plain" and body_text is None:
                    body_text = GmailClient._decode_payload(part)
        else:
            ctype = msg.get_content_type()
            payload = GmailClient._decode_payload(msg)
            if ctype == "text/html":
                body_html = payload
            else:
                body_text = payload

        return body_html, body_text

    @staticmethod
    def _decode_payload(part: Message) -> str | None:
        payload = part.get_payload(decode=True)
        if payload is None:
            return None
        charset = part.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            return payload.decode("utf-8", errors="replace")

    def mark_as_read(self, uid: str) -> None:
        self.conn.uid("STORE", uid, "+FLAGS", "(\\Seen)")

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            self.conn.logout()
        except Exception:
            pass
