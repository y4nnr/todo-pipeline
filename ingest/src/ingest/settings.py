from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
INGEST_ROOT = REPO_ROOT / "ingest"


class Settings(BaseSettings):
    # Loads both the top-level .env (Postgres/Vikunja infra) and ingest/.env (API keys)
    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), str(INGEST_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Postgres (ingest DB — used for idempotency)
    ingest_db_host: str = "127.0.0.1"
    ingest_db_port: int = 5432
    ingest_db_name: str = "ingest"
    ingest_db_user: str
    ingest_db_password: str

    # Google / Gmail / Pub/Sub
    gcp_project_id: str = "todo-pipeline"
    pubsub_subscription: str = "gmail-todo-sub"
    gmail_user: str
    gmail_subject_prefix: str = "todo"   # case-insensitive match
    gmail_credentials_path: Path = INGEST_ROOT / "credentials.json"
    gmail_token_path: Path = INGEST_ROOT / "token.json"
    gmail_processed_label: str = "Processed/Vikunja"
    google_application_credentials: Path = INGEST_ROOT / "service-account.json"

    # Anthropic
    anthropic_api_key: str
    anthropic_model: str = "claude-haiku-4-5"

    # Vikunja
    vikunja_api_url: str = "http://localhost:3456/api/v1"
    vikunja_api_token: str
    vikunja_default_project_id: int = 1

    # Bucket → project ID mapping (override via .env if you move projects around)
    bucket_todo_project_id: int = 1
    bucket_toread_project_id: int = 2
    bucket_towatch_project_id: int = 3
    bucket_tobuy_project_id: int = 4
    bucket_tolearn_project_id: int = 6

    # Alerting (ntfy.sh public). Topic string = auth — keep secret.
    ntfy_url: str = "https://ntfy.sh"
    ntfy_topic: str | None = None  # disabled if unset

    # Runtime
    log_level: str = Field(default="INFO")
    pubsub_max_messages: int = 10

    @property
    def dsn(self) -> str:
        return (
            f"postgresql://{self.ingest_db_user}:{self.ingest_db_password}"
            f"@{self.ingest_db_host}:{self.ingest_db_port}/{self.ingest_db_name}"
        )

    @property
    def subscription_path(self) -> str:
        return f"projects/{self.gcp_project_id}/subscriptions/{self.pubsub_subscription}"


settings = Settings()  # type: ignore[call-arg]
