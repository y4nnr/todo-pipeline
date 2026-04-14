import base64
from datetime import datetime, timezone
from email.utils import parseaddr
from functools import lru_cache

from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials

from .logging import log
from .models import EmailPayload
from .settings import settings

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


@lru_cache(maxsize=1)
def _session() -> AuthorizedSession:
    creds = Credentials.from_authorized_user_file(str(settings.gmail_token_path), SCOPES)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        settings.gmail_token_path.write_text(creds.to_json())
    return AuthorizedSession(creds)


def _get(path: str, **params) -> dict:
    r = _session().get(f"{BASE}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _post(path: str, json: dict) -> dict:
    r = _session().post(f"{BASE}{path}", json=json, timeout=30)
    r.raise_for_status()
    return r.json()


def list_new_message_ids(start_history_id: int) -> tuple[list[str], int | None]:
    """Return (new message IDs since checkpoint, latest historyId seen)."""
    message_ids: list[str] = []
    latest = start_history_id
    page_token: str | None = None
    while True:
        params = {
            "startHistoryId": str(start_history_id),
            "historyTypes": "messageAdded",
            "labelId": "INBOX",
        }
        if page_token:
            params["pageToken"] = page_token
        r = _session().get(f"{BASE}/history", params=params, timeout=30)
        if r.status_code == 404:
            log.warning("gmail.history.expired", start_history_id=start_history_id)
            return [], None
        r.raise_for_status()
        resp = r.json()
        for h in resp.get("history", []):
            latest = max(latest, int(h.get("id", latest)))
            for m in h.get("messagesAdded", []):
                mid = m.get("message", {}).get("id")
                if mid:
                    message_ids.append(mid)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return message_ids, latest


def get_latest_history_id() -> int:
    return int(_get("/profile")["historyId"])


def fetch_message(message_id: str) -> EmailPayload | None:
    msg = _get(f"/messages/{message_id}", format="full")
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    subject = headers.get("subject", "")
    from_addr = parseaddr(headers.get("from", ""))[1].lower()
    to_addr = parseaddr(headers.get("to", ""))[1].lower()
    received_at = datetime.fromtimestamp(int(msg["internalDate"]) / 1000, tz=timezone.utc)
    body = _extract_body(msg.get("payload", {}))
    return EmailPayload(
        message_id=message_id,
        thread_id=msg.get("threadId", ""),
        subject=subject,
        from_addr=from_addr,
        to_addr=to_addr,
        received_at=received_at,
        body=body,
    )


def matches_filter(email: EmailPayload) -> bool:
    from . import buckets
    sender_ok = email.from_addr == settings.gmail_user.lower()
    bucket_ok = buckets.match(email.subject) is not None
    return sender_ok and bucket_ok


def add_label(message_id: str, label_name: str) -> None:
    label_id = _ensure_label(label_name)
    _post(
        f"/messages/{message_id}/modify",
        {"addLabelIds": [label_id], "removeLabelIds": ["UNREAD"]},
    )


def _ensure_label(name: str) -> str:
    labels = _get("/labels").get("labels", [])
    for lab in labels:
        if lab["name"] == name:
            return lab["id"]
    created = _post(
        "/labels",
        {"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
    )
    return created["id"]


def _extract_body(payload: dict) -> str:
    parts = _flatten_parts(payload)
    plain = next((p for p in parts if p.get("mimeType") == "text/plain"), None)
    if plain:
        return _decode(plain.get("body", {}).get("data", ""))
    html = next((p for p in parts if p.get("mimeType") == "text/html"), None)
    if html:
        import re
        return re.sub(r"<[^>]+>", " ", _decode(html.get("body", {}).get("data", "")))
    return _decode(payload.get("body", {}).get("data", ""))


def _flatten_parts(payload: dict) -> list[dict]:
    out: list[dict] = []
    stack = [payload]
    while stack:
        p = stack.pop()
        if "parts" in p:
            stack.extend(p["parts"])
        else:
            out.append(p)
    return out


def _decode(data: str) -> str:
    if not data:
        return ""
    return base64.urlsafe_b64decode(data.encode()).decode("utf-8", errors="replace")
