from anthropic import Anthropic

from .models import EmailPayload, ExtractedTask
from .settings import settings

_client = Anthropic(api_key=settings.anthropic_api_key)

_SYSTEM_BASE = """You turn an informal self-email into a clean structured task for a todo app.

Rules:
- The user writes short stream-of-consciousness notes. Distill them.
- title: ≤80 chars, no leading routing prefix (td/tr/tw/tb/todo/…)
- description: keep useful context from the body; empty string if none
- due_date: ISO-8601 date or datetime if the email implies a deadline; null otherwise
- priority: 1=low, 3=medium, 4=high, 5=urgent. Default to 1 (low).
  Only raise priority if the email explicitly uses an urgency expression:
    * "medium" / "normal" / "soon" → 3
    * "high" / "important" / "priority" → 4
    * "urgent" / "ASAP" / "critical" / "today" / "now" / "emergency" → 5
  If no such expression is present, keep priority at 1 regardless of the bucket or content.
- Respond ONLY by calling the create_task tool. No prose.
"""

_BUCKET_HINTS = {
    "todo":    "Bucket: TODO — an actionable task. Title should be imperative (e.g. 'Call the dentist').",
    "toread":  "Bucket: TO READ — article / blog / paper to read later. Title names the topic or source (e.g. 'Article: Rust async performance'). due_date usually null.",
    "towatch": "Bucket: TO WATCH — video / talk / film. Title names the item (e.g. 'Talk: Simple Made Easy by Rich Hickey'). due_date usually null.",
    "tobuy":   "Bucket: TO BUY — shopping item. Title is the item (e.g. 'Oat milk'). due_date only if explicitly needed by a date.",
    "tolearn": "Bucket: TO LEARN — course / tutorial / skill or topic to study. Title names the subject or resource (e.g. 'Learn: Rust ownership model'). due_date only if there's a deadline (exam, cohort start).",
}

_TOOL = {
    "name": "create_task",
    "description": "Create a structured Vikunja task from the email.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "minLength": 1, "maxLength": 250},
            "description": {"type": "string"},
            "due_date": {
                "type": ["string", "null"],
                "description": "ISO-8601 date or datetime, or null",
            },
            "priority": {"type": "integer", "minimum": 1, "maximum": 5},
        },
        "required": ["title", "description", "priority"],
    },
}


def extract_task(email: EmailPayload, bucket_key: str = "todo", cleaned_subject: str | None = None) -> ExtractedTask:
    subj = cleaned_subject if cleaned_subject is not None else email.subject
    system = _SYSTEM_BASE + "\n" + _BUCKET_HINTS.get(bucket_key, _BUCKET_HINTS["todo"])
    user_msg = f"Subject: {subj}\n\nBody:\n{email.body[:8000]}"
    resp = _client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=system,
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "create_task"},
        messages=[{"role": "user", "content": user_msg}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == "create_task":
            return ExtractedTask.model_validate(block.input)
    raise RuntimeError("Claude did not return a create_task tool call")
