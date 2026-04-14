# todo-pipeline

A self-hosted pipeline that turns prefixed emails into tasks in
[Vikunja](https://vikunja.io/) using Claude for extraction.

```
Gmail  →  Pub/Sub  →  Python ingest  →  Claude (Anthropic)  →  Vikunja
```

Send yourself a message like `td: call the plumber tomorrow at 9am`, and a
structured task appears in the right Vikunja project a few seconds later.

## Features

- **Push-based ingest** — Gmail `watch()` publishes to Pub/Sub; no polling.
- **Multi-bucket routing** — subject prefixes route to different Vikunja
  projects:
  - `td:` / `todo:` → Todo (Inbox)
  - `tr:` / `toread:` → To read
  - `tw:` / `towatch:` → To watch
  - `tb:` / `tobuy:` → To buy
  - `tl:` / `tolearn:` → To learn
- **Claude-powered extraction** — title, description, due date, priority are
  inferred from natural-language subject + body via Anthropic tool-use.
- **Idempotent & durable** — Postgres tracks every message id, so retries
  never double-create. Successful messages are labelled in Gmail.
- **Production-ready** — runs under `systemd` with restart-on-failure, a
  weekly Gmail `watch()` renewal timer, a daily heartbeat check, and
  error / liveness alerting via [ntfy.sh](https://ntfy.sh).

## Architecture

| Component | Role |
| --- | --- |
| `ingest/` | Python service: Pub/Sub subscriber, Gmail fetch, Claude extraction, Vikunja API client |
| `db/` | Postgres init scripts (Vikunja DB + ingest dedup DB) |
| `docker-compose.yml` | Postgres + Vikunja containers |
| `ingest/systemd/` | `.example` unit files for the ingest service, heartbeat, and watch renewal |

## Quick start

1. **Google Cloud setup** — create a project, enable the Gmail API + Pub/Sub,
   create a topic + subscription, grant `gmail-api-push@...` publish rights
   on the topic. Download a service-account key and OAuth client credentials.
2. **Configure** — copy `.env.example` → `.env` (repo root) and
   `ingest/.env.example` → `ingest/.env`; fill in values.
3. **Bring up Vikunja + Postgres:**
   ```bash
   docker compose up -d
   ```
4. **Install the ingest service** — see [`ingest/README.md`](ingest/README.md)
   for the Python setup, one-time OAuth consent, and systemd install steps.
5. **Register the Gmail watch():**
   ```bash
   cd ingest && .venv/bin/python setup_watch.py
   ```

## Security notes

- All secrets live in `.env` files — **never** commit them.
- OAuth tokens, GCP service-account keys, and credential JSONs are
  `.gitignore`d by default.
- The Pub/Sub subscriber authenticates with an explicit service-account
  JSON, so the service works under `systemd` without ambient auth.

## License

MIT
