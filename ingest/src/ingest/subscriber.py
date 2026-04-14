import json
from concurrent.futures import TimeoutError as FuturesTimeout

from google.cloud import pubsub_v1
from google.oauth2 import service_account

from . import db, gmail_client
from .logging import log
from .processor import process_message
from .settings import settings


def _on_message(msg: pubsub_v1.subscriber.message.Message) -> None:
    """Pub/Sub callback. Gmail pushes {emailAddress, historyId}."""
    try:
        payload = json.loads(msg.data.decode("utf-8"))
        history_id = int(payload["historyId"])
    except (ValueError, KeyError, json.JSONDecodeError):
        log.warning("subscriber.bad_payload", data=msg.data[:200])
        msg.ack()
        return

    log.info("subscriber.notification", history_id=history_id)
    last = db.get_last_history_id()
    if last is None:
        # Bootstrap: skip everything before this notification, store checkpoint
        db.set_last_history_id(history_id)
        msg.ack()
        return

    new_ids, latest = gmail_client.list_new_message_ids(start_history_id=last)
    if latest is None:
        # History expired — reset to current
        bootstrap = gmail_client.get_latest_history_id()
        db.set_last_history_id(bootstrap)
        msg.ack()
        return

    failed = False
    for mid in new_ids:
        try:
            process_message(mid)
        except Exception:  # noqa: BLE001
            failed = True
            # error already logged + persisted in processor

    if failed:
        # nack so Pub/Sub redelivers; processed_messages dedup prevents reprocessing
        msg.nack()
        return

    db.set_last_history_id(max(latest, history_id))
    msg.ack()


PUBSUB_SCOPES = ["https://www.googleapis.com/auth/pubsub"]


def _load_sa_credentials() -> service_account.Credentials:
    """Explicitly load the Pub/Sub service account. No reliance on $GOOGLE_APPLICATION_CREDENTIALS
    at runtime — path comes from settings and must be readable before any client is built."""
    path = settings.google_application_credentials
    if not path.is_file():
        raise FileNotFoundError(
            f"Pub/Sub service account key not found at {path}. "
            "Set google_application_credentials in settings / .env."
        )
    return service_account.Credentials.from_service_account_file(str(path), scopes=PUBSUB_SCOPES)


def run() -> None:
    db.init_schema()
    credentials = _load_sa_credentials()
    log.info(
        "subscriber.credentials.loaded",
        sa_path=str(settings.google_application_credentials),
        sa_email=getattr(credentials, "service_account_email", "unknown"),
    )
    subscriber = pubsub_v1.SubscriberClient(credentials=credentials)
    flow_control = pubsub_v1.types.FlowControl(max_messages=settings.pubsub_max_messages)
    log.info("subscriber.start", subscription=settings.subscription_path)
    future = subscriber.subscribe(
        settings.subscription_path, callback=_on_message, flow_control=flow_control
    )
    try:
        future.result()
    except (KeyboardInterrupt, FuturesTimeout):
        future.cancel()
        future.result()
    finally:
        subscriber.close()
        log.info("subscriber.stop")
