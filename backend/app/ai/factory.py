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

    client: StructuredLLM = (
        GeminiClient(key) if settings.ai_provider == "gemini" else ClaudeClient(key)
    )
    return FallbackLLM(client) if settings.ai_fallback_to_rules else client
