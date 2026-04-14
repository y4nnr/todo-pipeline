"""Metadata-only alerting via ntfy.sh.

Security: payloads must NEVER contain email subject/body, task titles, or any
content from the user's inbox. Only categories, counts, message IDs, and
timestamps. If ntfy operator ever logs, nothing sensitive leaks.
"""
from __future__ import annotations

import time
from threading import Lock

import httpx

from .logging import log
from .settings import settings

_RATE_LIMIT_SECONDS = 15 * 60          # per-category cooldown
_last_sent: dict[str, float] = {}
_lock = Lock()


def notify(category: str, message: str, priority: str = "default") -> None:
    """Send a metadata-only alert. Same category won't re-fire within 15 min.

    priority: "min" | "low" | "default" | "high" | "urgent"
    """
    if not settings.ntfy_topic:
        log.debug("alerts.disabled", category=category)
        return

    with _lock:
        now = time.monotonic()
        last = _last_sent.get(category, 0.0)
        if now - last < _RATE_LIMIT_SECONDS:
            log.debug("alerts.ratelimited", category=category)
            return
        _last_sent[category] = now

    url = f"{settings.ntfy_url.rstrip('/')}/{settings.ntfy_topic}"
    try:
        httpx.post(
            url,
            content=message.encode("utf-8"),
            headers={
                "Title": f"ingest: {category}",
                "Priority": priority,
                "Tags": "warning,gear",
            },
            timeout=5.0,
        ).raise_for_status()
        log.info("alerts.sent", category=category, priority=priority)
    except Exception:  # noqa: BLE001 — alerting must never crash the caller
        log.exception("alerts.failed", category=category)
