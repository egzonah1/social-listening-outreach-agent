"""The Gemini version of the AI interface (Google's official `google-genai` SDK).

We use Gemini because its free tier needs no payment card. Free-tier prompts
may be used by Google to improve its products, which is acceptable here only
because we send nothing but public posts.

Structured outputs: we pass the Pydantic model's JSON schema, Gemini answers
with JSON in that shape, and we validate it again with Pydantic.
"""

import logging
from typing import TypeVar

import httpx2 as httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from app.ai.client import AIError, Effort

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

THINKING: dict[Effort, types.ThinkingLevel] = {
    "low": types.ThinkingLevel.LOW,
    "medium": types.ThinkingLevel.MEDIUM,
    "high": types.ThinkingLevel.HIGH,
}
# Finish reasons that mean Gemini blocked the answer for safety or policy reasons.
BLOCKED = {
    types.FinishReason.SAFETY,
    types.FinishReason.PROHIBITED_CONTENT,
    types.FinishReason.BLOCKLIST,
    types.FinishReason.SPII,
}
# The free tier allows ~15 requests a minute: retry rate limits and server errors.
RETRIES = types.HttpRetryOptions(
    attempts=3, initial_delay=2.0, http_status_codes=[429, 500, 502, 503, 504]
)


class GeminiClient:
    def __init__(self, api_key: str, http_client: httpx.Client | None = None) -> None:
        options = types.HttpOptions(timeout=90_000, retry_options=RETRIES)  # timeout in ms
        if http_client is not None:  # tests inject a client with a fake network
            options = types.HttpOptions(timeout=90_000, httpx_client=http_client)
        self._client = genai.Client(api_key=api_key, http_options=options)

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
        try:
            response = self._client.models.generate_content(
                model=model, contents=user, config=config
            )
        except errors.ClientError as exc:
            raise _client_error(exc) from exc
        except errors.APIError as exc:
            logger.error("Gemini API error %s: %s", exc.code, exc.message)
            raise AIError(f"The AI service returned an error ({exc.code}).") from exc
        except httpx.TransportError as exc:
            raise AIError("Could not reach the AI service.") from exc

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


def _client_error(exc: errors.ClientError) -> AIError:
    if exc.code in (401, 403) or "API key" in (exc.message or ""):
        return AIError("The Gemini API key is invalid.")
    if exc.code == 429:
        return AIError("The AI free-tier limit was reached. Please try again later.")
    logger.error("Gemini rejected the request %s: %s", exc.code, exc.message)
    return AIError(f"The AI service rejected the request ({exc.code}).")
