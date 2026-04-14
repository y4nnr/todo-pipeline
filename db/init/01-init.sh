#!/bin/bash
# Runs on first Postgres container start. Creates vikunja + ingest DBs/users
# and the processed_messages table used for idempotency.
set -euo pipefail

: "${VIKUNJA_DB_USER:?}"
: "${VIKUNJA_DB_PASSWORD:?}"
: "${VIKUNJA_DB_NAME:=vikunja}"
: "${INGEST_DB_USER:?}"
: "${INGEST_DB_PASSWORD:?}"
: "${INGEST_DB_NAME:=ingest}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
    CREATE USER ${VIKUNJA_DB_USER} WITH PASSWORD '${VIKUNJA_DB_PASSWORD}';
    CREATE DATABASE ${VIKUNJA_DB_NAME} OWNER ${VIKUNJA_DB_USER};

    CREATE USER ${INGEST_DB_USER} WITH PASSWORD '${INGEST_DB_PASSWORD}';
    CREATE DATABASE ${INGEST_DB_NAME} OWNER ${INGEST_DB_USER};

    \\connect ${INGEST_DB_NAME}

    CREATE TABLE processed_messages (
        gmail_message_id TEXT PRIMARY KEY,
        processed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
        vikunja_task_id  BIGINT,
        status           TEXT NOT NULL CHECK (status IN ('created', 'skipped', 'error')),
        error_message    TEXT
    );

    CREATE INDEX idx_processed_messages_status
        ON processed_messages (status, processed_at DESC);

    ALTER TABLE processed_messages OWNER TO ${INGEST_DB_USER};
SQL
