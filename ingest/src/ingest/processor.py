from . import alerts, buckets, claude_client, db, gmail_client, vikunja_client
from .logging import log
from .settings import settings


def process_message(message_id: str) -> None:
    """Process a single Gmail message ID end-to-end. Idempotent."""
    if not db.claim_message(message_id):
        log.info("processor.skip.duplicate", message_id=message_id)
        return

    try:
        email = gmail_client.fetch_message(message_id)
        if email is None:
            db.mark_result(message_id, "skipped", error_message="not found")
            return

        if email.from_addr != settings.gmail_user.lower():
            log.info("processor.skip.sender", message_id=message_id, from_addr=email.from_addr)
            db.mark_result(message_id, "skipped", error_message="sender")
            return

        match = buckets.match(email.subject)
        if match is None:
            log.info(
                "processor.skip.no_bucket",
                message_id=message_id,
                subject=email.subject[:60],
            )
            db.mark_result(message_id, "skipped", error_message="no_bucket")
            return
        bucket, cleaned_subject = match

        task = claude_client.extract_task(email, bucket_key=bucket.key, cleaned_subject=cleaned_subject)
        task_id = vikunja_client.create_task(task, project_id=bucket.project_id)
        gmail_client.add_label(message_id, "Processed/Vikunja")
        db.mark_result(message_id, "created", vikunja_task_id=task_id)
        log.info(
            "processor.created",
            message_id=message_id,
            vikunja_task_id=task_id,
            bucket=bucket.key,
            project_id=bucket.project_id,
            title=task.title,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("processor.error", message_id=message_id)
        db.mark_result(message_id, "error", error_message=str(e)[:500])
        category = _classify(e)
        # Metadata-only: error class + truncated message (no email content)
        alerts.notify(
            category,
            f"{type(e).__name__}: {str(e)[:160]}",
            priority="high",
        )
        raise


def _classify(e: BaseException) -> str:
    name = type(e).__name__.lower()
    mod = type(e).__module__.lower()
    if "anthropic" in mod or "claude" in name:
        return "claude_error"
    if "httpx" in mod or "httpstatus" in name:
        return "vikunja_error"
    if "psycopg" in mod:
        return "db_error"
    if "google" in mod or "grpc" in mod:
        return "google_error"
    return "unknown_error"
