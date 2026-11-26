"""Application settings, read from environment variables (and a local .env file).

Every setting the app needs lives here, so there is one place to look and
nothing reads os.environ directly. Pydantic validates the values at startup:
a typo such as LOG_LEVEL=LOUD fails immediately instead of at 2 a.m.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The name saved on results produced by the keyword rules instead of an AI model.
RULES_MODEL = "rules"


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

    # AI. Gemini is the default because its free tier needs no payment card.
    # "rules" runs without any AI service (keyword rules and reply templates).
    ai_provider: Literal["gemini", "anthropic", "rules"] = "gemini"
    # If the AI fails (e.g. the free daily limit is used up), use the rules instead.
    ai_fallback_to_rules: bool = True

    # Secrets use SecretStr so they never appear in logs or error messages.
    gemini_api_key: SecretStr | None = None
    # Chosen from a speed test on Nov 26: the Flash-Lite models answered in 1-5 s,
    # while the bigger Flash models were often overloaded (503) or timed out (504).
    gemini_draft_model: str = "gemini-3.5-flash-lite"
    gemini_triage_model: str = "gemini-3.5-flash-lite"
    # Tried in order when the main model is busy or slow (comma-separated).
    gemini_draft_backup_models: str = "gemini-3.1-flash-lite,gemini-3.5-flash"
    gemini_triage_backup_models: str = "gemini-3.1-flash-lite"

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

    # Folder with the built React app (`npm run build`). Empty means
    # "<repo>/frontend/dist". If the folder is missing, only the API is served.
    frontend_dist: str = ""

    # Public demo protection (see app/api/guards.py). Empty ACCESS_CODE = open
    # (fine on your own computer). Limits of 0 switch that limit off.
    access_code: SecretStr | None = None
    searches_per_hour: int = Field(default=10, ge=0)
    searches_per_day_total: int = Field(default=100, ge=0)
    ai_actions_per_hour: int = Field(default=60, ge=0)
    ai_actions_per_day_total: int = Field(default=400, ge=0)

    # Speed. After sorting, replies for the best posts are written in the background,
    # so nobody waits when opening a post. Each AI call gets a hard time limit;
    # after it, the backup model or the rules answer instead.
    predraft_limit: int = Field(default=8, ge=0, le=50)
    ai_time_budget_seconds: float = Field(default=45.0, ge=5.0, le=300.0)

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, url: str) -> str:
        """Neon and Render hand out "postgresql://..." (or "postgres://...") URLs.
        SQLAlchemy needs the driver name, so add it instead of failing at startup."""
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url.removeprefix(prefix)
        return url

    @property
    def triage_model(self) -> str:
        return {
            "gemini": self.gemini_triage_model,
            "anthropic": self.claude_triage_model,
            "rules": RULES_MODEL,
        }[self.ai_provider]

    @property
    def draft_model(self) -> str:
        return {
            "gemini": self.gemini_draft_model,
            "anthropic": self.claude_draft_model,
            "rules": RULES_MODEL,
        }[self.ai_provider]


@lru_cache
def get_settings() -> Settings:
    """Return one shared Settings instance (read once, then cached)."""
    return Settings()
