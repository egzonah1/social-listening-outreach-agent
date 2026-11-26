"""Builds the AI client the settings ask for."""

import logging

from app.ai.client import ClaudeClient, StructuredLLM
from app.ai.gemini import GeminiClient
from app.ai.rules import FallbackLLM, RuleBasedLLM
from app.core.config import Settings

logger = logging.getLogger(__name__)


def build_ai_client(settings: Settings) -> StructuredLLM | None:
    """Returns None when there is no AI key and the rules backup is switched off."""
    if settings.ai_provider == "rules":
        return RuleBasedLLM()

    secret = (
        settings.gemini_api_key if settings.ai_provider == "gemini" else settings.anthropic_api_key
    )
    key = secret.get_secret_value() if secret else ""
    if not key:
        return RuleBasedLLM() if settings.ai_fallback_to_rules else None

    client: StructuredLLM
    if settings.ai_provider == "gemini":
        backups = {
            settings.gemini_draft_model: _names(settings.gemini_draft_backup_models),
            settings.gemini_triage_model: _names(settings.gemini_triage_backup_models),
        }
        client = GeminiClient(
            key, backup_models=backups, time_budget_seconds=settings.ai_time_budget_seconds
        )
    else:
        client = ClaudeClient(key)
    return FallbackLLM(client) if settings.ai_fallback_to_rules else client


def _names(comma_separated: str) -> list[str]:
    return [name.strip() for name in comma_separated.split(",") if name.strip()]
