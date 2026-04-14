import httpx

from .logging import log
from .models import ExtractedTask
from .settings import settings


def create_task(task: ExtractedTask, project_id: int | None = None) -> int:
    pid = project_id or settings.vikunja_default_project_id
    payload: dict = {
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
    }
    if task.due_date is not None:
        # Vikunja expects RFC3339 with timezone (e.g. 2026-04-20T00:00:00Z)
        dt = task.due_date
        if dt.tzinfo is None:
            from datetime import timezone
            dt = dt.replace(tzinfo=timezone.utc)
        payload["due_date"] = dt.isoformat().replace("+00:00", "Z")

    r = httpx.put(
        f"{settings.vikunja_api_url}/projects/{pid}/tasks",
        json=payload,
        headers={"Authorization": f"Bearer {settings.vikunja_api_token}"},
        timeout=15.0,
    )
    if r.status_code >= 400:
        log.error(
            "vikunja.create_task.failed",
            status=r.status_code,
            body=r.text[:500],
            payload=payload,
        )
        r.raise_for_status()
    return int(r.json()["id"])
