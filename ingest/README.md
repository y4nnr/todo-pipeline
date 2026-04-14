# ingest

Gmail (`watch` API) → Pub/Sub → Python → Claude → Vikunja.

## Install

```bash
cd /path/to/todo/ingest
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## OAuth (one-time, and after scope changes)

The scope is `gmail.modify` (needed to apply the `Processed/Vikunja` label).
Re-consent if you previously authorized only `gmail.readonly`:

```bash
rm token.json
python auth.py     # opens browser
```

## Run (manual)

```bash
python -m ingest
```

## Run (systemd)

Copy the example unit files and edit the `User`, `Group`, and path placeholders
to match your environment:

```bash
cp systemd/ingest.service.example /etc/systemd/system/ingest.service
sudo $EDITOR /etc/systemd/system/ingest.service
sudo systemctl daemon-reload
sudo systemctl enable --now ingest
journalctl -u ingest -f
```

## Renew Gmail `watch()` (weekly, required)

`watch()` expires after 7 days. Either install the systemd timer
(`ingest-watch-renew.timer.example`) or add a cron entry (see
`systemd/renew-watch.cron.example`).

## Filter

A message is processed only if **both**:
- `From` matches the address configured in `GMAIL_USER`
- `Subject` starts (case-insensitive) with one of the configured prefixes
  (`td`/`tr`/`tw`/`tb` — routing to Todo / To read / To watch / To buy)

Skipped messages are still recorded in `processed_messages` with `status='skipped'` so they're never re-evaluated.

## Layout

```
src/ingest/
├── settings.py       # pydantic-settings, loads ../.env + ./.env
├── logging.py        # structlog JSON
├── models.py         # EmailPayload, ExtractedTask
├── db.py             # Postgres dedup + history checkpoint
├── gmail_client.py   # history list, fetch, filter, label
├── claude_client.py  # Anthropic SDK, structured tool-use
├── vikunja_client.py # PUT /api/v1/projects/{id}/tasks
├── processor.py      # claim → fetch → filter → extract → create → label
├── subscriber.py     # Pub/Sub pull loop
└── __main__.py
```
