"""Gmail API wrapper — OAuth, list/get/send messages, label management."""
from __future__ import annotations
import base64
import logging
import mimetypes
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import settings

log = logging.getLogger(__name__)


class GmailClient:
    """A small Gmail API wrapper covering exactly what the watcher needs."""

    def __init__(self) -> None:
        self.service = self._authenticate()
        self._label_cache: dict[str, str] = {}

    # ── Auth ─────────────────────────────────────────────────────────────
    def _authenticate(self):
        settings.validate()
        creds: Optional[Credentials] = None

        if settings.TOKEN_FILE.exists():
            try:
                creds = Credentials.from_authorized_user_file(
                    str(settings.TOKEN_FILE), settings.SCOPES
                )
            except Exception as e:
                log.warning("Cached token unreadable, re-authenticating: %s", e)
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                log.info("Refreshing Gmail OAuth token…")
                creds.refresh(Request())
            else:
                log.info("Starting OAuth consent flow (a browser tab will open)…")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(settings.CLIENT_SECRET_FILE), settings.SCOPES
                )
                # Print the URL explicitly in case the browser doesn't auto-open.
                # We have to do this before run_local_server() blocks.
                auth_url, _ = flow.authorization_url(prompt="consent")
                log.info(
                    "────────────────────────────────────────────────────────────\n"
                    "  If a browser tab doesn't open, paste this URL into one:\n"
                    "  %s\n"
                    "────────────────────────────────────────────────────────────",
                    auth_url,
                )
                creds = flow.run_local_server(port=0, prompt="consent",
                                              open_browser=True,
                                              authorization_prompt_message="")
            settings.TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
            log.info("Saved token to %s", settings.TOKEN_FILE)

        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    # ── Profile ──────────────────────────────────────────────────────────
    def me(self) -> str:
        """Return the authenticated account's email address."""
        return self.service.users().getProfile(userId="me").execute()["emailAddress"]

    # ── Labels ───────────────────────────────────────────────────────────
    def get_or_create_label(self, name: str) -> str:
        """Return label ID for `name`, creating nested labels as needed."""
        if name in self._label_cache:
            return self._label_cache[name]
        existing = self.service.users().labels().list(userId="me").execute().get("labels", [])
        for lab in existing:
            if lab["name"] == name:
                self._label_cache[name] = lab["id"]
                return lab["id"]
        body = {
            "name": name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }
        created = self.service.users().labels().create(userId="me", body=body).execute()
        log.info("Created Gmail label %r (id=%s)", name, created["id"])
        self._label_cache[name] = created["id"]
        return created["id"]

    def add_label(self, message_id: str, label_id: str) -> None:
        self.service.users().messages().modify(
            userId="me", id=message_id, body={"addLabelIds": [label_id]}
        ).execute()

    # ── List + fetch ─────────────────────────────────────────────────────
    def list_candidate_messages(self) -> list[str]:
        """List unread inbox messages with attachments not yet processed."""
        processed_label_id = self.get_or_create_label(settings.LABEL_PROCESSED)
        skipped_label_id = self.get_or_create_label(settings.LABEL_SKIPPED)
        # Gmail search query
        q = (
            "in:inbox is:unread has:attachment "
            f"newer_than:{settings.LOOKBACK_DAYS}d "
            f"-label:{settings.LABEL_PROCESSED.replace(' ', '-')} "
            f"-label:{settings.LABEL_SKIPPED.replace(' ', '-')}"
        )
        try:
            resp = self.service.users().messages().list(
                userId="me",
                q=q,
                maxResults=settings.MAX_MESSAGES_PER_POLL,
            ).execute()
        except HttpError as e:
            log.error("Gmail list failed: %s", e)
            return []
        msgs = resp.get("messages", [])
        return [m["id"] for m in msgs]

    def get_message(self, msg_id: str) -> dict:
        return self.service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()

    def get_attachment_bytes(self, msg_id: str, attachment_id: str) -> bytes:
        att = self.service.users().messages().attachments().get(
            userId="me", messageId=msg_id, id=attachment_id
        ).execute()
        data = att.get("data", "")
        # Gmail returns URL-safe base64 without padding sometimes
        padded = data + "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(padded)

    # ── Send ─────────────────────────────────────────────────────────────
    def send_reply(
        self,
        to: str,
        subject: str,
        html_body: str,
        in_reply_to_msg_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        attachments: Optional[list[tuple[str, bytes, str]]] = None,
    ) -> dict:
        """Send a reply email. `attachments` is list of (filename, bytes, mime)."""
        msg = EmailMessage()
        msg["To"] = to
        msg["From"] = self.me()
        msg["Subject"] = subject
        msg.set_content("This message contains HTML — please view in an HTML-capable client.")
        msg.add_alternative(html_body, subtype="html")

        if in_reply_to_msg_id:
            msg["In-Reply-To"] = in_reply_to_msg_id
            msg["References"] = in_reply_to_msg_id

        for fname, data, mime in (attachments or []):
            maintype, _, subtype = (mime or "application/octet-stream").partition("/")
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=fname)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
        body: dict = {"raw": raw}
        if thread_id:
            body["threadId"] = thread_id
        return self.service.users().messages().send(userId="me", body=body).execute()


# ── Helpers to navigate the message payload ──────────────────────────────────

def header(msg: dict, name: str) -> str:
    """Return a header value (case-insensitive) from the parsed message."""
    name_low = name.lower()
    for h in msg.get("payload", {}).get("headers", []):
        if h["name"].lower() == name_low:
            return h["value"]
    return ""


def walk_parts(payload: dict) -> Iterable[dict]:
    """Yield every part in a Gmail payload tree (DFS)."""
    yield payload
    for part in payload.get("parts", []) or []:
        yield from walk_parts(part)


def extract_attachments_meta(msg: dict) -> list[dict]:
    """Return [{filename, mime, size, attachment_id}, …] for attachments."""
    out: list[dict] = []
    for part in walk_parts(msg.get("payload", {})):
        filename = part.get("filename") or ""
        body = part.get("body") or {}
        att_id = body.get("attachmentId")
        if filename and att_id:
            out.append({
                "filename": filename,
                "mime": part.get("mimeType", "application/octet-stream"),
                "size": int(body.get("size", 0)),
                "attachment_id": att_id,
            })
    return out
