"""Application settings, read from environment variables (and a local .env file).

Every setting the app needs lives here, so there is one place to look and
nothing reads os.environ directly. Pydantic validates the values at startup:
a typo such as LOG_LEVEL=LOUD fails immediately instead of at 2 a.m.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Look for .env in the backend folder and in the repo root.
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Social Listening Outreach Agent"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Local default matches docker-compose.yml. Production sets DATABASE_URL to Neon.
    database_url: str = "postgresql+psycopg://outreach:outreach@localhost:5433/outreach"

    # Secrets use SecretStr so they never appear in logs or error messages.
    anthropic_api_key: SecretStr | None = None
    claude_draft_model: str = "claude-opus-5-5"
    claude_triage_model: str = "claude-haiku-5-5"

    bluesky_handle: str | None = None
    bluesky_app_password: SecretStr | None = None

    # Data protection. Bluesky's developer guidelines ask apps to publish a contact
    # address and to delete content on request; collected posts are also deleted
    # automatically after `retention_days`.
    contact_email: str | None = None
    retention_days: int = Field(default=30, ge=1, le=365)


@lru_cache
def get_settings() -> Settings:
    """Return one shared Settings instance (read once, then cached)."""
    return Settings()
