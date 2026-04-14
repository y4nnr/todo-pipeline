"""Register / renew the Gmail watch() so notifications flow into the Pub/Sub topic.
Safe to run repeatedly — each call replaces the previous watch (resets the 7-day clock).
Exits non-zero on failure so systemd marks the unit failed and journald/alerts flag it.
"""
import json
import sys
from datetime import datetime, timezone

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

TOKEN_PATH = "token.json"
TOPIC = "projects/todo-pipeline/topics/gmail-todo-notifications"

try:
    creds = Credentials.from_authorized_user_file(TOKEN_PATH)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    result = service.users().watch(
        userId="me",
        body={"labelIds": ["INBOX"], "topicName": TOPIC},
    ).execute()
    expiration_ms = int(result.get("expiration", 0))
    expires_at = datetime.fromtimestamp(expiration_ms / 1000, tz=timezone.utc).isoformat()
    print(json.dumps({
        "event": "watch.renewed",
        "historyId": result.get("historyId"),
        "expiration": expires_at,
    }))
except Exception as e:  # noqa: BLE001
    print(json.dumps({"event": "watch.failed", "error": str(e)}), file=sys.stderr)
    sys.exit(1)
