"""The Gemini version of the AI interface (Google's official `google-genai` SDK).

We use Gemini because its free tier needs no payment card. Free-tier prompts
may be used by Google to improve its products, which is acceptable here only
because we send nothing but public posts.

Structured outputs: we pass the Pydantic model's JSON schema, Gemini answers
with JSON in that shape, and we validate it again with Pydantic.

Reliability on the free tier (found in the live test on Nov 26): models are
sometimes overloaded (503) or the connection drops. So each call is retried,
and if the model stays unavailable we try a backup model (e.g. 3.5-flash when
3.8-flash is busy). Only after that does the app fall back to the rules.
"""

import logging
import time
from collections.abc import Callable, Mapping
from typing import TypeVar

import httpx2 as httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from app.ai.client import AIError, Effort

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Low thinking levels keep the free tier fast enough for a person waiting on
# the screen: sorting and short replies don't need long reasoning.
THINKING: dict[Effort, types.ThinkingLevel] = {
    "low": types.ThinkingLevel.MINIMAL,
    "medium": types.ThinkingLevel.LOW,
    "high": types.ThinkingLevel.MEDIUM,
}
# Finish reasons that mean Gemini blocked the answer for safety or policy reasons.
BLOCKED = {
    types.FinishReason.SAFETY,
    types.FinishReason.PROHIBITED_CONTENT,
    types.FinishReason.BLOCKLIST,
    types.FinishReason.SPII,
}
# Busy or temporarily broken: worth retrying, or trying another model.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
ATTEMPTS_PER_MODEL = 2
RETRY_DELAY_SECONDS = 2.0
TIMEOUT_MS = 120_000


class AIUnavailable(AIError):
    """The model is busy or unreachable right now; another try may work."""


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        *,
        backup_models: Mapping[str, str] | None = None,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        # We retry ourselves (below), so the SDK's own retries are off. It also
        # doesn't retry dropped connections, which we saw in the live test.
        options = types.HttpOptions(timeout=TIMEOUT_MS, httpx_client=http_client)
        self._client = genai.Client(api_key=api_key, http_options=options)
        self._backup_models = dict(backup_models or {})
        self._sleep = sleep  # tests pass a no-op so they don't wait
        # Read by `model_used()`, so results are saved with the model that answered.
        self.last_model_used: str | None = None

    def parse(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: type[T],
        effort: Effort = "medium",
        max_tokens: int = 4000,
    ) -> T:
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_json_schema=schema.model_json_schema(),
            max_output_tokens=max_tokens,
            thinking_config=types.ThinkingConfig(thinking_level=THINKING[effort]),
        )
        backup = self._backup_models.get(model)
        models = [model] if backup in (None, model) else [model, backup]
        last_error: AIUnavailable | None = None
        for current in models:
            for attempt in range(ATTEMPTS_PER_MODEL):
                try:
                    result = self._call(current, user, config, schema)
                except AIUnavailable as exc:
                    logger.warning("Gemini %s unavailable (try %d): %s", current, attempt + 1, exc)
                    last_error = exc
                    if attempt + 1 < ATTEMPTS_PER_MODEL:
                        self._sleep(RETRY_DELAY_SECONDS * (attempt + 1))
                    continue
                self.last_model_used = current
                return result
        assert last_error is not None
        raise last_error

    def _call(
        self, model: str, user: str, config: types.GenerateContentConfig, schema: type[T]
    ) -> T:
        try:
            response = self._client.models.generate_content(
                model=model, contents=user, config=config
            )
        except errors.APIError as exc:
            raise _api_error(exc) from exc
        except httpx.TransportError as exc:  # dropped connection, timeout, DNS ...
            raise AIUnavailable("Could not reach the AI service.") from exc

        if response.prompt_feedback and response.prompt_feedback.block_reason:
            raise AIError("The AI declined to process this content.")
        candidate = response.candidates[0] if response.candidates else None
        if candidate is None:
            raise AIError("The AI returned no answer. Please try again.")
        if candidate.finish_reason in BLOCKED:
            raise AIError("The AI declined to process this content.")
        if candidate.finish_reason == types.FinishReason.MAX_TOKENS:
            raise AIError("The AI response was incomplete. Please try again.")
        try:
            return schema.model_validate_json(response.text or "")
        except ValidationError as exc:
            raise AIError("The AI declined or returned an unreadable response.") from exc


def _api_error(exc: errors.APIError) -> AIError:
    if exc.code in (401, 403) or "API key" in (exc.message or ""):
        return AIError("The Gemini API key is invalid.")
    if exc.code == 429:
        return AIUnavailable("The AI free-tier limit was reached. Please try again later.")
    if exc.code in RETRYABLE_STATUS:
        logger.error("Gemini API error %s: %s", exc.code, exc.message)
        return AIUnavailable(f"The AI service is busy or returned an error ({exc.code}).")
    logger.error("Gemini rejected the request %s: %s", exc.code, exc.message)
    return AIError(f"The AI service rejected the request ({exc.code}).")
