"""Subject-prefix routing. Short codes (td/tr/tw/tb) + long forms all supported."""
from __future__ import annotations

from dataclasses import dataclass

from .settings import settings


@dataclass(frozen=True)
class Bucket:
    key: str               # canonical name, used in logs + Claude prompt hints
    project_id: int
    aliases: tuple[str, ...]   # lowercase prefixes; match is case-insensitive + needs trailing space


BUCKETS: tuple[Bucket, ...] = (
    Bucket("todo",    settings.bucket_todo_project_id,    ("td", "todo")),
    Bucket("toread",  settings.bucket_toread_project_id,  ("tr", "toread")),
    Bucket("towatch", settings.bucket_towatch_project_id, ("tw", "towatch")),
    Bucket("tobuy",   settings.bucket_tobuy_project_id,   ("tb", "tobuy")),
    Bucket("tolearn", settings.bucket_tolearn_project_id, ("tl", "tolearn")),
)


def match(subject: str) -> tuple[Bucket, str] | None:
    """If the subject starts with a known prefix followed by a space, return
    (bucket, cleaned_subject). Returns None if no bucket matches."""
    s = subject.strip()
    lower = s.lower()
    for bucket in BUCKETS:
        for alias in bucket.aliases:
            if lower.startswith(alias + " ") or lower == alias:
                cleaned = s[len(alias):].strip()
                return bucket, cleaned
    return None
