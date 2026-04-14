"""Daily self-check. Looks at processed_messages for recent activity;
alerts if the pipeline has been silent too long (likely dead Gmail watch()
or subscription issue).

Run by systemd timer, not by the long-running ingest process.
"""
from __future__ import annotations

from datetime import timedelta

from . import alerts, db
from .logging import configure_logging, log

SILENT_THRESHOLD_HOURS = 36  # watch() is renewed weekly; real silence > 1 day is suspect


def main() -> None:
    configure_logging()
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS total, "
            "COUNT(*) FILTER (WHERE status='error') AS errors, "
            "MAX(processed_at) AS last_seen "
            "FROM processed_messages "
            "WHERE processed_at > now() - interval '36 hours'"
        )
        row = cur.fetchone()

    total = row["total"]
    errors = row["errors"]
    last_seen = row["last_seen"]

    log.info("heartbeat.summary", total=total, errors=errors, last_seen=str(last_seen))

    if total == 0:
        alerts.notify(
            "silent_pipeline",
            f"no Pub/Sub activity in {SILENT_THRESHOLD_HOURS}h — check gmail watch() + subscription",
            priority="urgent",
        )
        return

    if errors > 0:
        alerts.notify(
            "error_summary",
            f"{errors}/{total} messages errored in last 24h",
            priority="default",
        )


if __name__ == "__main__":
    main()
