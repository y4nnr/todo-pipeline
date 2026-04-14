from datetime import datetime

from pydantic import BaseModel, Field


class ExtractedTask(BaseModel):
    """Structured task produced by Claude from a raw email."""

    title: str = Field(min_length=1, max_length=250)
    description: str = ""
    due_date: datetime | None = None
    priority: int = Field(default=0, ge=0, le=5)


class EmailPayload(BaseModel):
    """Raw email fetched from Gmail, fed to Claude."""

    message_id: str
    thread_id: str
    subject: str
    from_addr: str
    to_addr: str
    received_at: datetime
    body: str
