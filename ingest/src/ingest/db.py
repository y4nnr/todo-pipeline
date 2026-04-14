from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from .settings import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_messages (
    gmail_message_id TEXT PRIMARY KEY,
    processed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    vikunja_task_id  BIGINT,
    status           TEXT NOT NULL CHECK (status IN ('created', 'skipped', 'error')),
    error_message    TEXT
);

CREATE INDEX IF NOT EXISTS idx_processed_messages_status
    ON processed_messages (status, processed_at DESC);

CREATE TABLE IF NOT EXISTS gmail_state (
    id              INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    last_history_id BIGINT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def init_schema() -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(_SCHEMA)


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    with psycopg.connect(settings.dsn, row_factory=dict_row, autocommit=True) as conn:
        yield conn


def claim_message(message_id: str) -> bool:
    """Reserve a Gmail message ID. Returns True if newly claimed, False if already processed."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO processed_messages (gmail_message_id, status) "
            "VALUES (%s, 'skipped') ON CONFLICT DO NOTHING RETURNING gmail_message_id",
            (message_id,),
        )
        return cur.fetchone() is not None


def mark_result(
    message_id: str,
    status: str,
    vikunja_task_id: int | None = None,
    error_message: str | None = None,
) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE processed_messages "
            "SET status = %s, vikunja_task_id = %s, error_message = %s, processed_at = now() "
            "WHERE gmail_message_id = %s",
            (status, vikunja_task_id, error_message, message_id),
        )


def get_last_history_id() -> int | None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT last_history_id FROM gmail_state WHERE id = 1")
        row = cur.fetchone()
        return row["last_history_id"] if row else None


def set_last_history_id(history_id: int) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO gmail_state (id, last_history_id) VALUES (1, %s) "
            "ON CONFLICT (id) DO UPDATE SET last_history_id = EXCLUDED.last_history_id, "
            "updated_at = now() "
            "WHERE gmail_state.last_history_id IS NULL "
            "   OR EXCLUDED.last_history_id > gmail_state.last_history_id",
            (history_id,),
        )
